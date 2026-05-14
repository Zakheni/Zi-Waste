# -*- coding: utf-8 -*-
import json
import re
import logging
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote
# -*- coding: utf-8 -*-
import re
import logging
from typing import Any, Dict, List, Optional, Union

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)
_JSON = "application/json"

# ===== Aliases (extend freely) =====
_KEY_ALIASES: Dict[str, List[str]] = {
    "phone": [
        "phone","telephone","telephone1","telephone2","tel","cell","mobile","mobile1","mobile2",
        "phone_number","contact_no","contact_number","workphone","work_phone","homephone","home_phone",
        "phoneno","phone_no","phonenumber","phone1","phone2",
        "contact.phone","contact.phone1","contact.telephone","contact.telephone1","contact.mobile",
        "primarycontact.phone","primarycontact.telephone","primarycontact.mobile",
        "contacts[0].phone","contacts[0].mobile","contacts[0].telephone",
        "Phone","Telephone","Telephone1","Telephone2","Cell","Mobile","PhoneNumber","Phone1","Phone2",
        "Contact.Phone","Contact.Telephone","Contact.Telephone1","Contact.Mobile",
        "PrimaryContact.Phone","PrimaryContact.Telephone","PrimaryContact.Mobile",
    ],
    "email": [
        "email","e_mail","e-mail","mail","email_address","email1","email2",
        "contact.email","primarycontact.email","contacts[0].email",
        "Email","E_Mail","E-mail","Mail","EmailAddress","Email1","Email2",
        "Contact.Email","PrimaryContact.Email",
    ],
    "addr1": ["address1","Address1","addr1","Addr1","AddressLine1","Street","Street1"],
    "addr2": ["address2","Address2","addr2","Addr2","AddressLine2","Street2"],
    "addr3": ["address3","Address3","addr3","Addr3","City","Town","Suburb"],
    "addr4": ["address4","Address4","addr4","Addr4","State","Province","Region"],
    "postal": ["postal_code","PostalCode","zip","Zip","ZipCode","Postal"],
    "country_code": ["country_code","CountryCode","Country","CountryISO","ISO2","ISO3"],
    "name": ["name","Name","customer_name","CustomerName","display_name","DisplayName"],
    "code": ["code","Code","customer_code","CustomerCode","AccountCode","Account","AccCode"],
    "tax_code": ["tax_code","TaxCode","VAT","Vat","vat"],
    "currency_code": ["currency_code","CurrencyCode","Currency"],
    "credit_limit": ["credit_limit","CreditLimit"],
    "balance": ["balance","Balance","Outstanding"],
}

# ===== Deep utilities =====
def _iter_items(obj: Any):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield str(i), v

def _ci_eq(a: str, b: str) -> bool:
    return isinstance(a, str) and isinstance(b, str) and a.lower() == b.lower()

def _normalize_alias(alias: str) -> List[str]:
    # keep segments including [0] as part of the segment
    return alias.split(".")

def _deep_find_parts(obj: Any, parts: List[str]) -> Any:
    if not parts:
        return obj
    head, *tail = parts

    # segment like 'contacts[0]'
    m = re.match(r"^(?P<name>[^\[]+)\[(?P<idx>\d+)\]$", head)
    if m:
        name = m.group("name"); idx = int(m.group("idx"))
        if isinstance(obj, dict):
            for k, v in obj.items():
                if _ci_eq(k, name):
                    if isinstance(v, (list, tuple)) and 0 <= idx < len(v):
                        return _deep_find_parts(v[idx], tail)
                    if isinstance(v, dict) and idx == 0:
                        return _deep_find_parts(v, tail)
        if isinstance(obj, (list, tuple)):
            for _, child in _iter_items(obj):
                res = _deep_find_parts(child, [head] + tail)
                if res is not None:
                    return res
        return None

    if isinstance(obj, dict):
        for k, v in obj.items():
            if _ci_eq(k, head):
                return _deep_find_parts(v, tail)
        # DFS search into children
        for _, v in obj.items():
            res = _deep_find_parts(v, [head] + tail)
            if res is not None:
                return res

    if isinstance(obj, (list, tuple)):
        for _, v in _iter_items(obj):
            res = _deep_find_parts(v, [head] + tail)
            if res is not None:
                return res

    return None

def _deep_pick(d: Any, keys: List[str]) -> Any:
    for k in keys:
        val = _deep_find_parts(d, _normalize_alias(k))
        if val is not None:
            return val
    return None

# ===== Regex fallbacks (scan any string in the record) =====
_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
# keep +country and digits; SA numbers typically 10 digits (0xx… or +27…)
_PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{6,}\d)")

def _flatten_strings(obj: Any, out: List[str]):
    """Collect *all* strings from any depth for regex scanning."""
    if obj is None:
        return
    if isinstance(obj, str):
        s = obj.strip()
        if s:
            out.append(s)
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _flatten_strings(v, out)
        return
    if isinstance(obj, (list, tuple)):
        for v in obj:
            _flatten_strings(v, out)
        return
    # other scalars
    try:
        s = str(obj).strip()
        if s:
            out.append(s)
    except Exception:
        pass

def _scan_any_email(obj: Any) -> Optional[str]:
    buf: List[str] = []
    _flatten_strings(obj, buf)
    for s in buf:
        m = _EMAIL_RE.search(s)
        if m:
            return m.group(0)
    return None

def _scan_any_phone(obj: Any) -> Optional[str]:
    buf: List[str] = []
    _flatten_strings(obj, buf)
    for s in buf:
        m = _PHONE_RE.search(s)
        if m:
            raw = m.group(1)
            # normalize: keep digits + leading +
            cleaned = re.sub(r"[^\d+]", "", raw)
            # basic sanity
            if len(re.sub(r"\D", "", cleaned)) >= 7:
                return cleaned
    return None

# ===== Odoo model =====
class PastelSync(models.Model):
    _name = "pastel.sync"
    _description = "Pastel Sync Helper"

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True
    )

    # --- cleaners ---
    def _clean(self, v: Any) -> Any:
        if v is None:
            return False
        s = str(v).replace("\u00A0", " ").strip()
        return s or False

    def _clean_phone(self, v: Any) -> Any:
        if not v:
            return False
        s = str(v).strip()
        s = re.sub(r"[^\d+]", "", s)
        return s or False

    def _clean_email(self, v: Any) -> Any:
        if not v:
            return False
        s = str(v).strip()
        return s if _EMAIL_RE.fullmatch(s) or _EMAIL_RE.search(s) else False

    def _prune_empty(self, vals: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in vals.items() if v not in (False, None, "")}

    # --- config/http ---
    def _conf(self) -> (str, str):
        S = self.env["pastel.connector.setting"].sudo().search([], limit=1)
        if not S or not S.pastel_api_base or not S.pastel_api_key:
            raise UserError(_("Configure Bridge URL/API Key in Pastel Connector > Configuration"))
        return S.pastel_api_base.rstrip("/"), S.pastel_api_key

    def _req(self, method: str, path: str, key: str, base: str, **kw) -> Any:
        url = f"{base}{path}"
        headers = kw.pop("headers", {})
        headers["x-api-key"] = key
        try:
            r = requests.request(method, url, headers=headers, timeout=120, **kw)
            r.raise_for_status()
        except requests.RequestException as e:
            raise UserError(_("Bridge request failed: %s") % e)
        ctype = (r.headers.get("Content-Type") or "").lower()
        if ctype.startswith(_JSON):
            return r.json()
        return r.text

    @api.model
    def pastel_test_connection(self) -> bool:
        base, key = self._conf()
        self._req("GET", "/health", key, base)
        return True

    def _log(self, kind: str, created: int, updated: int) -> None:
        msg = f"Pastel {kind} import: created={created}, updated={updated}"
        _logger.info(msg)
        S = self.env["pastel.connector.setting"].sudo().search([], limit=1)
        if S and hasattr(S, "message_post"):
            S.message_post(body=msg)

    # --- unwrap list from dicts like {"data":[...]}, {"items":[...]}, etc ---
    def _unwrap_list(self, payload: Any) -> List[Any]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "items", "results", "customers", "Records", "records"):
                if key in payload and isinstance(payload[key], list):
                    return payload[key]
        raise UserError(_("Bridge /customers did not return a list. Got: %s") % type(payload).__name__)

    # --- main import ---
    def import_customers(self) -> Dict[str, int]:
        base, key = self._conf()
        raw = self._req("GET", "/customers", key, base)
        data = self._unwrap_list(raw)

        Partner = self.env["res.partner"].sudo()
        Country = self.env["res.country"].sudo()

        ci = cu = 0
        for c in data:
            if not isinstance(c, (dict, list)):
                continue

            code = self._clean(_deep_pick(c, _KEY_ALIASES["code"]))
            if not code:
                _logger.debug("Skipped record without code. Keys: %s", list(c.keys()) if isinstance(c, dict) else type(c).__name__)
                continue

            street   = self._clean(_deep_pick(c, _KEY_ALIASES["addr1"]))
            street2  = self._clean(_deep_pick(c, _KEY_ALIASES["addr2"]))
            city     = self._clean(_deep_pick(c, _KEY_ALIASES["addr3"]))
            state_tx = self._clean(_deep_pick(c, _KEY_ALIASES["addr4"]))
            zip_code = self._clean(_deep_pick(c, _KEY_ALIASES["postal"]))

            country_id = False
            cc = self._clean(_deep_pick(c, _KEY_ALIASES["country_code"]))
            if cc:
                country = Country.search([("code", "=", cc)], limit=1)
                country_id = country.id if country else False

            # 1) try alias deep-pick
            phone_in = _deep_pick(c, _KEY_ALIASES["phone"])
            email_in = _deep_pick(c, _KEY_ALIASES["email"])
            # 2) regex scan anywhere if missing
            if not phone_in:
                phone_in = _scan_any_phone(c)
            if not email_in:
                email_in = _scan_any_email(c)

            phone = self._clean_phone(phone_in)
            email = self._clean_email(email_in)

            vals = {
                "name": self._clean(_deep_pick(c, _KEY_ALIASES["name"])) or code,
                "phone": phone,
                "email": email,
                "customer_rank": 1,
                "street": street,
                "street2": street2,
                "city": city,
                "state_id": False,
                "zip": zip_code,
                "country_id": country_id,
                "x_pastel_code": code,
                "x_pastel_tax_code": self._clean(_deep_pick(c, _KEY_ALIASES["tax_code"])),
                "x_pastel_currency_code": self._clean(_deep_pick(c, _KEY_ALIASES["currency_code"])),
                "x_pastel_credit_limit": float(_deep_pick(c, _KEY_ALIASES["credit_limit"]) or 0.0),
                "x_pastel_balance": float(_deep_pick(c, _KEY_ALIASES["balance"]) or 0.0),
            }
            vals = self._prune_empty(vals)

            if not vals.get("phone") or not vals.get("email"):
                _logger.debug(
                    "Partner %s: phone_in=%r email_in=%r -> phone=%r email=%r  (top keys: %s)",
                    code, phone_in, email_in, vals.get("phone"), vals.get("email"),
                    (list(c.keys()) if isinstance(c, dict) else type(c).__name__),
                )

            p = Partner.search([("x_pastel_code", "=", code)], limit=1)
            if p:
                if not p.customer_rank:
                    vals["customer_rank"] = 1
                p.write(vals); cu += 1
            else:
                Partner.create(vals); ci += 1

        self._log("customer", ci, cu)
        return {"ci": ci, "cu": cu}


    def import_suppliers(self):
        base, key = self._conf()
        data = self._req("GET", "/suppliers", key, base)
        Partner = self.env["res.partner"].sudo()
        Country = self.env["res.country"].sudo()

        si = su = 0
        for s in data:
            code = (s.get("code") or s.get("guid") or "").strip()  # ← fallback to GUID
            if not code:
                continue

            country_id = False
            cc = self._clean(s.get("country_code"))
            if cc:
                country = Country.search([("code", "=", cc)], limit=1)
                country_id = country.id if country else False

            vals = {
                "name": self._clean(s.get("name")) or code,
                "supplier_rank": 1,
                "phone": self._clean_phone(s.get("phone")),
                "email": self._clean_email(s.get("email")),
                "country_id": country_id,
                "x_pastel_code": code,  # ← use the stable key (code or guid)
                "x_pastel_tax_code": self._clean(s.get("tax_code")),
                "x_pastel_currency_code": self._clean(s.get("currency_code")),
                "x_pastel_credit_limit": float(s.get("credit_limit") or 0.0),
                "x_pastel_balance": float(s.get("balance") or 0.0),
            }
            vals = self._prune_empty(vals)

            p = Partner.search([("x_pastel_code", "=", code)], limit=1)
            if p:
                if not p.supplier_rank:
                    vals["supplier_rank"] = 1
                p.write(vals);
                su += 1
            else:
                Partner.create(vals);
                si += 1

        self._log("supplier", si, su)
        return {"si": si, "su": su}

    def import_products(self):
        base, key = self._conf()
        data = self._req("GET", "/products", key, base)
        PT = self.env["product.template"].sudo()

        pi = pu = 0
        for pr in data:
            code = (pr.get("code") or "").strip()
            name = self._clean(pr.get("name")) or code
            if not code:
                continue

            vals = {
                "name": name,
                "x_pastel_item_code": code,
                "x_pastel_tax_code": self._clean(pr.get("tax_code")),
            }
            vals = self._prune_empty(vals)

            p = PT.search([("x_pastel_item_code", "=", code)], limit=1)
            if p:
                p.write(vals); pu += 1
            else:
                PT.create(vals); pi += 1

        self._log("product", pi, pu)
        return {"pi": pi, "pu": pu}

    # ---------------------
    # IMPORTS: INVOICES (headers + optional lines)
    # ---------------------
    def import_invoices(self):
        base, key = self._conf()
        data = self._req("GET", "/invoices", key, base)
        Move = self.env["account.move"].sudo()

        ii = iu = 0
        for inv in data:
            doc = (inv.get("doc_no") or "").strip()
            partner_code = inv.get("customer_code")
            if not doc or not partner_code:
                continue

            partner = self.env["res.partner"].search([("x_pastel_code", "=", partner_code)], limit=1)
            if not partner:
                # Skip invoices whose customer wasn't imported yet
                continue

            vals = {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "x_pastel_doc_no": doc,
                "invoice_line_ids": [],
            }

            lines = inv.get("lines") or []
            if lines:
                for L in lines:
                    vals["invoice_line_ids"].append((0, 0, {
                        "name": L.get("name") or "Sage line",
                        "quantity": float(L.get("quantity") or 1.0),
                        "price_unit": float(L.get("price_unit") or 0.0),
                    }))
            else:
                vals["invoice_line_ids"].append((0, 0, {
                    "name": inv.get("description") or "Sage import",
                    "quantity": 1.0,
                    "price_unit": float(inv.get("amount_total") or 0.0),
                }))

            m = Move.search([("x_pastel_doc_no", "=", doc)], limit=1)
            if m:
                m.write(vals); iu += 1
            else:
                Move.create(vals); ii += 1

        self._log("invoice", ii, iu)
        return {"ii": ii, "iu": iu}

    def import_all(self, customers=True, products=False, invoices=False, suppliers=False):
        res = {"ci": 0, "cu": 0, "pi": 0, "pu": 0, "ii": 0, "iu": 0, "si": 0, "su": 0}
        if customers:
            r = self.import_customers();
            res.update(r)
        if products:
            r = self.import_products();
            res.update(r)
        if invoices:
            r = self.import_invoices();
            res.update(r)
        if suppliers:
            r = self.import_suppliers();
            res.update(r)
        return res

    # ---------------------
    # Logging helper
    # ---------------------
    def _log(self, kind, imported, updated, deleted=0, notes=None):
        self.env["pastel.sync.log"].sudo().create({
            "kind": kind, "imported": imported, "updated": updated, "deleted": deleted, "notes": notes or ""
        })
        return True

    # =====================================================================
    #  EXPORTS (IDEMPOTENT, NO DUPLICATES)
    # =====================================================================

    # ---- tax-code resolver (string like "0"/"1")
    def _pastel_tax_code(self, line):
        tmpl = line.product_id.product_tmpl_id if line.product_id else False
        code = (tmpl and getattr(tmpl, "x_pastel_tax_code", False)) or False
        if code:
            return str(code).strip()

        taxes = line.tax_ids or (tmpl and tmpl.taxes_id) or self.env["account.tax"]
        tax = taxes[:1]
        tax = tax and tax[0] or False

        if tax:
            tax_code_on_tax = getattr(tax, "x_pastel_tax_code", False) or getattr(tax, "pastel_code", False)
            if tax_code_on_tax:
                return str(tax_code_on_tax).strip()
            try:
                percent = int(round(float(tax.amount or 0)))
            except Exception:
                percent = 0
            return {0: "0", 14: "1", 15: "1"}.get(percent, "0")
        return "0"

    def _pastel_partner_code(self, partner):
        return partner.x_pastel_code or partner.ref or str(partner.id)

    def _pastel_product_code(self, product):
        tmpl = product.product_tmpl_id
        return tmpl.x_pastel_item_code or product.default_code or tmpl.default_code or str(product.id)

    # ---- merge duplicate lines (product/name/price/tax)
    def _coalesce_lines_for_pastel(self, raw_lines):
        def _norm_name(s):
            return (s or "").strip()

        bucket = {}
        for ln in raw_lines or []:
            key = (
                (ln.get("product_code") or "").strip(),
                _norm_name(ln.get("label") or ln.get("name")),
                round(float(ln.get("price_unit") or 0.0), 4),
                str(ln.get("tax_code") if ln.get("tax_code") is not None else "0"),
            )
            if key not in bucket:
                bucket[key] = {
                    "product_code": key[0] or None,
                    "name": (ln.get("label") or ln.get("name") or "").strip(),
                    "quantity": float(ln.get("quantity") or 0.0),
                    "price_unit": key[2],
                    "tax_code": key[3],
                }
            else:
                bucket[key]["quantity"] += float(ln.get("quantity") or 0.0)

        out = []
        for v in bucket.values():
            n = (v.get("name") or "").lower()
            p = (v.get("product_code") or "").lower()
            if n == "sage import" and p == "sage import":
                continue
            out.append(v)
        return out

    # ---- build payload for bridge /invoices
    @api.model
    def _build_invoice_payload(self, move):
        move.ensure_one()
        if move.move_type not in ("out_invoice", "out_refund"):
            raise UserError(_("Only customer invoices/refunds can be exported to Sage."))

        cust_code = self._pastel_partner_code(move.partner_id)
        if not cust_code:
            raise UserError(_("Partner has no Sage code/ref: %s") % (move.partner_id.display_name,))

        # doc_no = move.x_pastel_doc_no or move.name or str(move.id)
        doc_no = str(move.id)
        payment_ref = move.payment_reference or move.ref or ""
        payment_terms_name = (move.invoice_payment_term_id and move.invoice_payment_term_id.name) or ""
        payment_terms_id = move.invoice_payment_term_id.id if move.invoice_payment_term_id else None
        currency = (move.currency_id and move.currency_id.name) or "ZAR"

        delivery_date = getattr(move, "delivery_date", False)
        delivery_date = delivery_date.isoformat() if delivery_date else (move.invoice_date and move.invoice_date.isoformat())

        lines = []
        for line in move.invoice_line_ids:
            if line.display_type in ("line_section", "line_note"):
                continue
            if getattr(line, "exclude_from_invoice_tab", False):
                continue

            prod_code = self._pastel_product_code(line.product_id) if line.product_id else None
            qty = float(line.quantity or 0.0)
            price = float(line.price_unit or 0.0)

            lines.append({
                "product_code": prod_code,
                "label": line.name or (line.product_id and line.product_id.display_name) or "Line",
                "quantity": qty,
                "price_unit": price,
                "subtotal_excl": float(line.price_subtotal or (qty * price)),
                "tax_excl": float(line.price_subtotal or (qty * price)),
                "total": float(line.price_subtotal or (qty * price)),
                "tax_code": self._pastel_tax_code(line),
            })

        lines = self._coalesce_lines_for_pastel(lines)

        payload = {
            "doc_no": doc_no,
            "invoice_date": move.invoice_date and move.invoice_date.isoformat(),
            "delivery_date": delivery_date,
            "customer_code": cust_code,
            "payment_reference": payment_ref,
            "payment_terms": payment_terms_name,
            "invoice_payment_term_id": payment_terms_id,
            "currency": currency,
            "amount_total_excl": float(move.amount_untaxed or 0.0),
            "tax_amount": float(move.amount_tax or 0.0),
            "amount_total": float(move.amount_total or 0.0),
            "document_type": 3 if move.move_type == "out_invoice" else 13,
            "lines": lines,
        }

        _logger.info("Pastel export payload for %s: %s", doc_no, json.dumps(payload, indent=2))
        return payload

    # ---- existence check against bridge
    def _bridge_invoice_exists(self, base, key, doc_no, doc_type):
        headers = {"x-api-key": key}
        try:
            r = requests.get(
                f"{base.rstrip('/')}/invoices/exists",
                headers=headers,
                params={"doc_no": doc_no, "doc_type": int(doc_type)},
                timeout=15,
            )
            r.raise_for_status()
            # j = r.json() if r.headers.get("Content-Type", "").startswith(JSON) else {}
            j = r.json() if r.headers.get("Content-Type", "").startswith(_JSON) else {}
            return bool(j.get("exists"))
        except Exception as e:
            raise UserError(_("Bridge exists-check failed: %s") % e)

    # ---- single export (NO DUPLICATES)
    @api.model
    def export_invoice(self, move_id):
        base, key = self._conf()
        Move = self.env["account.move"].sudo()
        move = Move.browse(move_id)
        if not move.exists():
            raise UserError(_("Invoice not found (id=%s).") % move_id)
        if move.move_type not in ("out_invoice", "out_refund") or move.state != "posted":
            raise UserError(_("Only posted customer invoices/credit notes can be exported."))

        payload = self._build_invoice_payload(move)
        doc_no   = payload.get("doc_no")
        doc_type = int(payload.get("document_type") or 3)
        if not doc_no:
            raise UserError(_("Missing doc_no in payload."))

        headers = {
            "x-api-key": key,
            "Content-Type": "application/json",
            "Idempotency-Key": f"odoo-{move.id}-{doc_no}-{doc_type}",
        }
        put_url  = f"{base.rstrip('/')}/invoices/{quote(doc_no, safe='')}"
        post_url = f"{base.rstrip('/')}/invoices"

        # Decide path: if we already stored a Sage number, assume exists; else ask bridge
        exists = bool(move.x_pastel_doc_no) or self._bridge_invoice_exists(base, key, doc_no, doc_type)

        try:
            if exists:
                resp = requests.put(put_url, json=payload, headers=headers, timeout=30)
                if resp.status_code == 404:              # deleted after our check -> create
                    resp = requests.post(post_url, json=payload, headers=headers, timeout=30)
                    if resp.status_code == 409:          # created concurrently -> update
                        resp = requests.put(put_url, json=payload, headers=headers, timeout=30)
            else:
                resp = requests.post(post_url, json=payload, headers=headers, timeout=30)
                if resp.status_code == 409:              # already exists (race) -> update
                    resp = requests.put(put_url, json=payload, headers=headers, timeout=30)
        except requests.RequestException as e:
            raise UserError(_("Bridge request failed: %s") % e)

        if not (200 <= resp.status_code < 300):
            raise UserError(_("Bridge error %s: %s") % (resp.status_code, resp.text))

        try:
            data = resp.json() if resp.text else {}
        except Exception:
            data = {}
        returned_no = data.get("doc_no") or doc_no
        if move.x_pastel_doc_no != returned_no:
            move.write({"x_pastel_doc_no": returned_no})

        self._log("invoice", 1, 0, notes=f"UPSERT invoice {returned_no}")
        _logger.info("Sage upsert OK: %s", returned_no)
        return True

    # ---- batch export with simple retry
    @api.model
    def export_invoices_by_ids(self, ids):
        results, exported, skipped = [], 0, 0
        Move = self.env["account.move"].sudo()
        moves = Move.browse(ids or []).exists()

        for move in moves:
            if move.move_type not in ("out_invoice", "out_refund") or move.state != "posted":
                results.append({
                    "id": move.id, "name": move.name, "ok": False,
                    "error": f"Unsupported or unposted move_type={move.move_type}"
                })
                skipped += 1
                continue

            attempts, max_attempts, last_err = 0, 2, None
            while attempts < max_attempts:
                attempts += 1
                try:
                    self.export_invoice(move.id)
                    exported += 1
                    results.append({
                        "id": move.id,
                        "name": move.name,
                        "ok": True,
                        "doc_no": move.x_pastel_doc_no or move.name,
                        "attempts": attempts,
                    })
                    break
                except Exception as e:
                    last_err = str(e)
                    transient = any(tok in last_err.lower() for tok in [
                        "timeout", "temporarily", "connection", "502", "503", "504"
                    ])
                    if attempts < max_attempts and transient:
                        time.sleep(1.0)
                        continue
                    skipped += 1
                    results.append({
                        "id": move.id, "name": move.name, "ok": False,
                        "error": last_err, "attempts": attempts,
                    })
                    break

        errors = [r.get("error") for r in results if not r.get("ok") and r.get("error")]
        return {
            "exported": exported,
            "skipped": skipped,
            "total": exported + skipped,
            "summary": {"exported": exported, "skipped": skipped, "total": exported + skipped},
            "results": results,
            "errors": errors,
        }

    # optional timestamp for incremental syncs
    last_sync_at = fields.Datetime(string="Last Sync At")



