# -*- coding: utf-8 -*-
import json
import re
import time
from urllib.parse import quote
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)
JSON = "application/json"


class PastelSync(models.Model):
    _name = "pastel.sync"
    _description = "Pastel Sync Helper"

    # ---------------------
    # Small clean helpers
    # ---------------------
    def _clean(self, v):
        if v is None:
            return False
        s = str(v).strip()
        return s or False

    def _clean_phone(self, v):
        s = self._clean(v)
        if not s:
            return False
        return re.sub(r"\s+", " ", s)

    def _clean_email(self, v):
        s = self._clean(v)
        if not s:
            return False
        s = s.replace("\u00A0", " ").strip()
        return s if "@" in s and "." in s else False

    def _prune_empty(self, vals: dict) -> dict:
        """Drop keys with False/None,'' so we don't overwrite good data with blanks."""
        return {k: v for k, v in vals.items() if v not in (False, None, "")}

    # ---------------------
    # Config & HTTP
    # ---------------------
    def _conf(self):
        S = self.env["pastel.connector.setting"].sudo().search([], limit=1)
        if not S or not S.pastel_api_base or not S.pastel_api_key:
            raise UserError(_("Configure Bridge URL/API Key in Pastel Connector > Configuration"))
        return S.pastel_api_base.rstrip("/"), S.pastel_api_key

    def _req(self, method, path, key, base, **kw):
        url = f"{base}{path}"
        headers = kw.pop("headers", {})
        headers["x-api-key"] = key
        r = requests.request(method, url, headers=headers, timeout=120, **kw)
        r.raise_for_status()
        if r.headers.get("Content-Type", "").startswith(JSON):
            return r.json()
        return r.text

    @api.model
    def pastel_test_connection(self):
        base, key = self._conf()
        self._req("GET", "/health", key, base)
        return True

    # ---------------------
    # IMPORTS: CUSTOMERS
    # ---------------------
    def import_customers(self):
        base, key = self._conf()
        data = self._req("GET", "/customers", key, base)
        Partner = self.env["res.partner"].sudo()
        Country = self.env["res.country"].sudo()

        ci = cu = 0
        for c in data:
            code = (c.get("code") or "").strip()
            if not code:
                continue

            street = self._clean(c.get("address1"))
            street2 = self._clean(c.get("address2"))
            city = self._clean(c.get("address3"))
            state = self._clean(c.get("address4"))
            zip_code = self._clean(c.get("postal_code"))

            country_id = False
            cc = self._clean(c.get("country_code"))
            if cc:
                country = Country.search([("code", "=", cc)], limit=1)
                country_id = country.id if country else False

            vals = {
                "name": self._clean(c.get("name")) or code,
                "phone": self._clean_phone(c.get("phone")),
                "email": self._clean_email(c.get("email")),
                "customer_rank": 1,
                "street": street,
                "street2": street2,
                "city": city,
                "state_id": False,
                "zip": zip_code,
                "country_id": country_id,
                "x_pastel_code": code,
                "x_pastel_tax_code": self._clean(c.get("tax_code")),
                "x_pastel_currency_code": self._clean(c.get("currency_code")),
                "x_pastel_credit_limit": float(c.get("credit_limit") or 0.0),
                "x_pastel_balance": float(c.get("balance") or 0.0),
            }
            vals = self._prune_empty(vals)

            p = Partner.search([("x_pastel_code", "=", code)], limit=1)
            if p:
                if not p.customer_rank:
                    vals["customer_rank"] = 1
                p.write(vals); cu += 1
            else:
                Partner.create(vals); ci += 1

        self._log("customer", ci, cu)
        return {"ci": ci, "cu": cu}

    # ---------------------
    # IMPORTS: SUPPLIERS
    # ---------------------

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

    # def import_suppliers(self):
    #     base, key = self._conf()
    #     # ask for more rows explicitly
    #     data = self._req("GET", "/suppliers?limit=5000", key, base)
    #     Partner = self.env["res.partner"].sudo()
    #     Country = self.env["res.country"].sudo()
    #
    #     total = len(data) if isinstance(data, list) else 0
    #     _logger.info("Pastel suppliers fetched: %s", total)
    #
    #     si = su = 0
    #     for s in (data or []):
    #         code = (s.get("code") or "").strip()
    #         if not code:
    #             continue
    #
    #         country_id = False
    #         cc = self._clean(s.get("country_code"))
    #         if cc:
    #             # most Pastel installs put numeric or blank here; keep it best-effort
    #             country = Country.search([("code", "=", cc)], limit=1)
    #             country_id = country.id if country else False
    #
    #         vals = {
    #             "name": self._clean(s.get("name")) or code,
    #             # make sure it’s treated as a supplier
    #             "supplier_rank": 1,
    #             "phone": self._clean_phone(s.get("phone")),
    #             "email": self._clean_email(s.get("email")),
    #             "country_id": country_id,
    #
    #             # reuse same code field used by customers to unify entities
    #             "x_pastel_code": code,
    #
    #             # extras
    #             "x_pastel_tax_code": self._clean(s.get("tax_code")),
    #             "x_pastel_currency_code": self._clean(s.get("currency_code")),
    #             "x_pastel_credit_limit": float(s.get("credit_limit") or 0.0),
    #             "x_pastel_balance": float(s.get("balance") or 0.0),
    #
    #             # optional niceties that sometimes help
    #             "company_type": "company",
    #             "is_company": True,
    #         }
    #         vals = self._prune_empty(vals)
    #
    #         p = Partner.search([("x_pastel_code", "=", code)], limit=1)
    #         if p:
    #             # ensure supplier role (increment rank if needed)
    #             if not p.supplier_rank:
    #                 vals["supplier_rank"] = 1
    #             p.write(vals)
    #             su += 1
    #         else:
    #             Partner.create(vals)
    #             si += 1
    #
    #     self._log("supplier", si, su)
    #     _logger.info("Pastel suppliers imported: created=%s, updated=%s (from=%s)", si, su, total)
    #     return {"si": si, "su": su}

    # def import_suppliers(self):
    #     base, key = self._conf()
    #     data = self._req("GET", "/suppliers", key, base)
    #     Partner = self.env["res.partner"].sudo()
    #     Country = self.env["res.country"].sudo()
    #
    #     si = su = 0
    #     for s in data:
    #         code = (s.get("code") or "").strip()
    #         if not code:
    #             continue
    #
    #         country_id = False
    #         cc = self._clean(s.get("country_code"))
    #         if cc:
    #             country = Country.search([("code", "=", cc)], limit=1)
    #             country_id = country.id if country else False
    #
    #         vals = {
    #             "name": self._clean(s.get("name")) or code,
    #             "supplier_rank": 1,
    #             "phone": self._clean_phone(s.get("phone")),
    #             "email": self._clean_email(s.get("email")),
    #             "country_id": country_id,
    #             "x_pastel_code": code,
    #             "x_pastel_tax_code": self._clean(s.get("tax_code")),
    #             "x_pastel_currency_code": self._clean(s.get("currency_code")),
    #             "x_pastel_credit_limit": float(s.get("credit_limit") or 0.0),
    #             "x_pastel_balance": float(s.get("balance") or 0.0),
    #         }
    #         vals = self._prune_empty(vals)
    #
    #         p = Partner.search([("x_pastel_code", "=", code)], limit=1)
    #         if p:
    #             if not p.supplier_rank:
    #                 vals["supplier_rank"] = 1
    #             p.write(vals); su += 1
    #         else:
    #             Partner.create(vals); si += 1
    #
    #     self._log("supplier", si, su)
    #     return {"si": si, "su": su}

    # ---------------------
    # IMPORTS: PRODUCTS
    # ---------------------
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
            j = r.json() if r.headers.get("Content-Type", "").startswith(JSON) else {}
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








# # pastel_sync.py
# import json
# import re
# import time
# from urllib.parse import quote
# import requests
# from odoo import models, fields, api, _
# from odoo.exceptions import UserError
# import logging
# _logger = logging.getLogger(__name__)
#
# JSON = "application/json"
#
# class PastelSync(models.Model):
#     _name = "pastel.sync"
#     _description = "Pastel Sync Helper"
#
#     # ---------------------
#     # Small clean helpers
#     # ---------------------
#     def _clean(self, v):
#         if v is None:
#             return False
#         s = str(v).strip()
#         return s or False
#
#     def _clean_phone(self, v):
#         s = self._clean(v)
#         if not s:
#             return False
#         # basic normalize: remove spaces/soft padding
#         return re.sub(r"\s+", " ", s)
#
#     def _clean_email(self, v):
#         s = self._clean(v)
#         if not s:
#             return False
#         # collapse giant space-only/placeholder strings
#         s = s.replace("\u00A0", " ").strip()
#         return s if "@" in s and "." in s else False
#
#     def _prune_empty(self, vals: dict) -> dict:
#         """Drop keys with False/None,'' so we don't overwrite good data with blanks."""
#         return {k: v for k, v in vals.items() if v not in (False, None, "")}
#
#     # ---------------------
#     # Bridge helpers
#     # ---------------------
#     def _conf(self):
#         S = self.env["pastel.connector.setting"].sudo().search([], limit=1)
#         if not S or not S.pastel_api_base or not S.pastel_api_key:
#             raise UserError(_("Configure Bridge URL/API Key in Pastel Connector > Configuration"))
#         return S.pastel_api_base.rstrip("/"), S.pastel_api_key
#
#     def _req(self, method, path, key, base, **kw):
#         url = f"{base}{path}"
#         headers = kw.pop("headers", {})
#         headers["x-api-key"] = key
#         r = requests.request(method, url, headers=headers, timeout=120, **kw)
#         r.raise_for_status()
#         if r.headers.get("Content-Type","").startswith(JSON):
#             return r.json()
#         return r.text
#
#     # ---------------------
#     # Connection test
#     # ---------------------
#     @api.model
#     def pastel_test_connection(self):
#         base, key = self._conf()
#         self._req("GET", "/health", key, base)
#         return True
#
#
#
#     # ---------------------
#     # IMPORTS: CUSTOMERS
#     # ---------------------
#     def import_customers(self):
#         base, key = self._conf()
#         data = self._req("GET", "/customers", key, base)
#         Partner = self.env["res.partner"].sudo()
#         Country = self.env["res.country"].sudo()
#
#         ci = cu = 0
#         for c in data:
#             code = (c.get("code") or "").strip()
#             if not code:
#                 continue
#
#             # map address → Odoo
#             street = self._clean(c.get("address1"))
#             street2 = self._clean(c.get("address2"))
#             city = self._clean(c.get("address3"))
#             state = self._clean(c.get("address4"))
#             zip_code = self._clean(c.get("postal_code"))
#
#             # country by ISO code if given
#             country_id = False
#             cc = self._clean(c.get("country_code"))
#             if cc:
#                 country = Country.search([("code", "=", cc)], limit=1)
#                 country_id = country.id if country else False
#
#             vals = {
#                 "name": self._clean(c.get("name")) or code,
#                 "phone": self._clean_phone(c.get("phone")),
#                 "email": self._clean_email(c.get("email")),
#                 "customer_rank": 1,
#                 "street": street,
#                 "street2": street2,
#                 "city": city,
#                 "state_id": False,    # you can wire a state resolver if you want
#                 "zip": zip_code,
#                 "country_id": country_id,
#
#                 # essentials
#                 "x_pastel_code": code,
#                 "x_pastel_tax_code": self._clean(c.get("tax_code")),
#                 "x_pastel_currency_code": self._clean(c.get("currency_code")),
#                 "x_pastel_credit_limit": float(c.get("credit_limit") or 0.0),
#                 "x_pastel_balance": float(c.get("balance") or 0.0),
#                 # "x_pastel_payment_terms": self._clean(c.get("payment_terms")),
#                 # "x_pastel_settlement_terms": self._clean(c.get("settlement_terms")),
#                 # "x_pastel_guid": self._clean(c.get("guid")),
#                 # "x_pastel_updated_on": self._clean(c.get("updated_on")),
#             }
#             vals = self._prune_empty(vals)
#
#             p = Partner.search([("x_pastel_code","=",code)], limit=1)
#             if p:
#                 # ensure it stays a customer
#                 if not p.customer_rank:
#                     vals["customer_rank"] = 1
#                 p.write(vals); cu += 1
#             else:
#                 Partner.create(vals); ci += 1
#
#         self._log("customer", ci, cu)
#         return {"ci": ci, "cu": cu}
#
#     # ---------------------
#     # IMPORTS: SUPPLIERS (NEW)
#     # ---------------------
#     def import_suppliers(self):
#         base, key = self._conf()
#         data = self._req("GET", "/suppliers", key, base)
#         Partner = self.env["res.partner"].sudo()
#         Country = self.env["res.country"].sudo()
#
#         si = su = 0
#         for s in data:
#             code = (s.get("code") or "").strip()
#             if not code:
#                 continue
#
#             country_id = False
#             cc = self._clean(s.get("country_code"))
#             if cc:
#                 country = Country.search([("code", "=", cc)], limit=1)
#                 country_id = country.id if country else False
#
#             vals = {
#                 "name": self._clean(s.get("name")) or code,
#                 "supplier_rank": 1,
#                 "phone": self._clean_phone(s.get("phone")),
#                 "email": self._clean_email(s.get("email")),
#                 "country_id": country_id,
#
#                 # reuse same key so a partner can be both customer & supplier
#                 "x_pastel_code": code,
#
#                 # essentials
#                 "x_pastel_tax_code": self._clean(s.get("tax_code")),
#                 "x_pastel_currency_code": self._clean(s.get("currency_code")),
#                 "x_pastel_credit_limit": float(s.get("credit_limit") or 0.0),
#                 "x_pastel_balance": float(s.get("balance") or 0.0),
#                 # "x_pastel_payment_terms": self._clean(s.get("payment_terms")),
#                 # "x_pastel_settlement_terms": self._clean(s.get("settlement_terms")),
#                 # # "x_pastel_guid": self._clean(s.get("guid")),
#                 # "x_pastel_updated_on": self._clean(s.get("updated_on")),
#             }
#             vals = self._prune_empty(vals)
#
#             p = Partner.search([("x_pastel_code","=",code)], limit=1)
#             if p:
#                 # keep/ensure supplier role
#                 if not p.supplier_rank:
#                     vals["supplier_rank"] = 1
#                 p.write(vals); su += 1
#             else:
#                 Partner.create(vals); si += 1
#
#         self._log("supplier", si, su)
#         return {"si": si, "su": su}
#
#     # ---------------------
#     # IMPORTS: PRODUCTS
#     # ---------------------
#     def import_products(self):
#         base, key = self._conf()
#         data = self._req("GET", "/products", key, base)
#         PT = self.env["product.template"].sudo()
#
#         pi = pu = 0
#         for pr in data:
#             code = (pr.get("code") or "").strip()
#             name = self._clean(pr.get("name")) or code
#             if not code:
#                 continue
#
#             vals = {
#                 "name": name,
#                 "x_pastel_item_code": code,
#                 "x_pastel_tax_code": self._clean(pr.get("tax_code")),
#                 # "x_pastel_category": self._clean(pr.get("category")),
#                 # "x_pastel_gl_code": self._clean(pr.get("gl_code")),
#                 # "x_pastel_guid": self._clean(pr.get("guid")),
#                 # "x_pastel_updated_on": self._clean(pr.get("updated_on")),
#             }
#             vals = self._prune_empty(vals)
#
#             p = PT.search([("x_pastel_item_code","=",code)], limit=1)
#             if p:
#                 p.write(vals); pu += 1
#             else:
#                 PT.create(vals); pi += 1
#
#         self._log("product", pi, pu)
#         return {"pi": pi, "pu": pu}
#
#     # ---------------------
#     # IMPORTS: INVOICES (unchanged logic)
#     # ---------------------
#     def import_invoices(self):
#         base, key = self._conf()
#         data = self._req("GET", "/invoices", key, base)
#         Move = self.env["account.move"].sudo()
#
#         ii = iu = 0
#         for inv in data:
#             doc = (inv.get("doc_no") or "").strip()
#             partner_code = inv.get("customer_code")
#             if not doc or not partner_code:
#                 continue
#
#             partner = self.env["res.partner"].search([("x_pastel_code","=",partner_code)], limit=1)
#             if not partner:
#                 # Skip invoices whose customer wasn't imported yet
#                 continue
#
#             vals = {
#                 "move_type": "out_invoice",
#                 "partner_id": partner.id,
#                 # "invoice_date": inv.get("invoice_date"),
#                 "x_pastel_doc_no": doc,
#                 # "x_pastel_document_type": inv.get("document_type"),
#                 "invoice_line_ids": [],
#             }
#
#             lines = inv.get("lines") or []
#             if lines:
#                 for L in lines:
#                     vals["invoice_line_ids"].append((0, 0, {
#                         "name": L.get("name") or "Sage line",
#                         "quantity": float(L.get("quantity") or 1.0),
#                         "price_unit": float(L.get("price_unit") or 0.0),
#                     }))
#             else:
#                 vals["invoice_line_ids"].append((0, 0, {
#                     "name": inv.get("description") or "Sage import",
#                     "quantity": 1.0,
#                     "price_unit": float(inv.get("amount_total") or 0.0),
#                 }))
#
#             m = Move.search([("x_pastel_doc_no","=",doc)], limit=1)
#             if m:
#                 m.write(vals); iu += 1
#             else:
#                 Move.create(vals); ii += 1
#
#         self._log("invoice", ii, iu)
#         return {"ii": ii, "iu": iu}
#
#     # ---------------------
#     # BATCH
#     # ---------------------
#     def import_all(self, customers=True, products=False, invoices=False, suppliers=False):
#         res = {"ci":0,"cu":0,"pi":0,"pu":0,"ii":0,"iu":0,"si":0,"su":0}
#         if customers:
#             r = self.import_customers(); res.update(r)
#         if products:
#             r = self.import_products(); res.update(r)
#         if invoices:
#             r = self.import_invoices(); res.update(r)
#         if suppliers:
#             r = self.import_suppliers(); res.update(r)
#         return res
#
#     # ---------------------
#     # Log helper
#     # ---------------------
#     def _log(self, kind, imported, updated, deleted=0, notes=None):
#         self.env["pastel.sync.log"].sudo().create({
#             "kind": kind, "imported": imported, "updated": updated, "deleted": deleted, "notes": notes or ""
#         })
#         return True
#
#     #     # ---------------------
#     #     # EXPORT HELPERS
#     #     # ---------------------
#     # @api.model
#     # def _pastel_partner_code(self, partner):
#     #     return partner.x_pastel_code or partner.ref or str(partner.id)
#     #
#     # @api.model
#     # def _pastel_product_code(self, product):
#     #     tmpl = product.product_tmpl_id
#     #     return tmpl.x_pastel_item_code or product.default_code or tmpl.default_code or str(product.id)
#     #
#     # def _pastel_tax_code(self, line):
#     #     tmpl = line.product_id.product_tmpl_id if line.product_id else False
#     #     code = (tmpl and getattr(tmpl, "x_pastel_tax_code", False)) or False
#     #     if code:
#     #         return str(code).strip()
#     #     taxes = line.tax_ids or (tmpl and tmpl.taxes_id) or self.env["account.tax"]
#     #     tax = taxes[:1]
#     #     tax = tax and tax[0] or False
#     #     if tax:
#     #         tax_code_on_tax = getattr(tax, "x_pastel_tax_code", False) or getattr(tax, "pastel_code", False)
#     #         if tax_code_on_tax:
#     #             return str(tax_code_on_tax).strip()
#     #         try:
#     #             percent = int(round(float(tax.amount or 0)))
#     #         except Exception:
#     #             percent = 0
#     #         return {0: "0", 14: "1", 15: "1"}.get(percent, "0")
#     #     return "0"
#     #
#     # def _coalesce_lines_for_pastel(self, raw_lines):
#     #     def _norm(s):
#     #         return (s or "").strip()
#     #
#     #     bucket = {}
#     #     for ln in raw_lines or []:
#     #         key = (
#     #             (ln.get("product_code") or "").strip(),
#     #             _norm(ln.get("label") or ln.get("name")),
#     #             round(float(ln.get("price_unit") or 0.0), 4),
#     #             str(ln.get("tax_code") if ln.get("tax_code") is not None else "0"),
#     #         )
#     #         if key not in bucket:
#     #             bucket[key] = {
#     #                 "product_code": key[0] or None,
#     #                 "name": _norm(ln.get("label") or ln.get("name")),
#     #                 "quantity": float(ln.get("quantity") or 0.0),
#     #                 "price_unit": key[2],
#     #                 "tax_code": key[3],
#     #             }
#     #         else:
#     #             bucket[key]["quantity"] += float(ln.get("quantity") or 0.0)
#     #     out = []
#     #     for v in bucket.values():
#     #         n = (v.get("name") or "").lower()
#     #         p = (v.get("product_code") or "").lower()
#     #         if n == "sage import" and p == "sage import":
#     #             continue
#     #         out.append(v)
#     #     return out
#     #
#     # @api.model
#     # def _build_invoice_payload(self, move):
#     #     """Payload built around a stable invoice_id to avoid duplicates."""
#     #     move.ensure_one()
#     #     if move.move_type not in ("out_invoice", "out_refund"):
#     #         raise UserError(_("Only customer invoices/refunds can be exported to Sage."))
#     #
#     #     cust_code = self._pastel_partner_code(move.partner_id)
#     #     if not cust_code:
#     #         raise UserError(_("Partner has no Sage code/ref: %s") % (move.partner_id.display_name,))
#     #
#     #     # STABLE EXTERNAL ID
#     #     invoice_id = str(move.id)
#     #
#     #     delivery_date = getattr(move, "delivery_date", False)
#     #     delivery_date = delivery_date.isoformat() if delivery_date else (
#     #                 move.invoice_date and move.invoice_date.isoformat())
#     #     payment_ref = move.payment_reference or move.ref or ""
#     #
#     #     lines = []
#     #     for line in move.invoice_line_ids:
#     #         if line.display_type in ("line_section", "line_note"):
#     #             continue
#     #         if getattr(line, "exclude_from_invoice_tab", False):
#     #             continue
#     #         prod_code = self._pastel_product_code(line.product_id) if line.product_id else None
#     #         qty = float(line.quantity or 0.0)
#     #         price = float(line.price_unit or 0.0)
#     #         lines.append({
#     #             "product_code": prod_code,
#     #             "label": line.name or (line.product_id and line.product_id.display_name) or "Line",
#     #             "quantity": qty,
#     #             "price_unit": price,
#     #             "subtotal_excl": float(line.price_subtotal or (qty * price)),
#     #             "tax_excl": float(line.price_subtotal or (qty * price)),
#     #             "total": float(line.price_subtotal or (qty * price)),
#     #             "tax_code": self._pastel_tax_code(line),
#     #         })
#     #
#     #     lines = self._coalesce_lines_for_pastel(lines)
#     #
#     #     payload = {
#     #         # NEW identity:
#     #         "invoice_id": invoice_id,
#     #         "invoice_date": move.invoice_date and move.invoice_date.isoformat(),
#     #         "delivery_date": delivery_date,
#     #         "customer_code": cust_code,
#     #         # store same ID on Sage reference column
#     #         "payment_reference": payment_ref,
#     #         "payment_terms": (move.invoice_payment_term_id and move.invoice_payment_term_id.name) or "",
#     #         "invoice_payment_term_id": move.invoice_payment_term_id.id if move.invoice_payment_term_id else None,
#     #         "currency": (move.currency_id and move.currency_id.name) or "ZAR",
#     #         "currency_id": move.currency_id and move.currency_id.id,
#     #         "amount_total_excl": float(move.amount_untaxed or 0.0),
#     #         "tax_amount": float(move.amount_tax or 0.0),
#     #         "amount_total": float(move.amount_total or 0.0),
#     #         "document_type": 3 if move.move_type == "out_invoice" else 13,
#     #         "lines": lines,
#     #     }
#     #
#     #     # _logger.info(
#     #     #         "Pastel export: invoice %s -> lines=%s (with_product=%s, display_skipped=%s, non_tab_skipped=%s)",
#     #     #         doc_no, len(lines), with_product, skipped_display, skipped_nontab
#     #     #     )
#     #     _logger.info("Pastel export payload for %s: %s", invoice_id, json.dumps(payload, indent=2))
#     #
#     #     return payload
#     #
#     # # optional: last sync field
#     # last_sync_at = fields.Datetime(string="Last Sync At")
#     #
#     # @api.model
#     # def export_invoice(self, move_id):
#     #     """Single idempotent upsert by invoice_id."""
#     #
#     #     base, key = self._conf()
#     #     Move = self.env["account.move"].sudo()
#     #     move = Move.browse(move_id)
#     #     if not move.exists():
#     #         raise UserError(_("Invoice not found (id=%s).") % move_id)
#     #     if move.move_type not in ("out_invoice", "out_refund") or move.state != "posted":
#     #         raise UserError(_("Only posted customer invoices/credit notes can be exported."))
#     #
#     #     payload = self._build_invoice_payload(move)
#     #
#     #     headers = {
#     #         "x-api-key": key,
#     #         "Content-Type": JSON,
#     #         "Idempotency-Key": f"odoo-{payload['invoice_id']}",
#     #     }
#     #     url = f"{base.rstrip('/')}/invoices/upsert"
#     #
#     #     try:
#     #         resp = requests.post(url, json=payload, headers=headers, timeout=40)
#     #     except requests.RequestException as e:
#     #         raise UserError(_("Bridge request failed: %s") % e)
#     #
#     #     if not (200 <= resp.status_code < 300):
#     #         raise UserError(_("Bridge error %s: %s") % (resp.status_code, resp.text))
#     #
#     #     # Mark exported using the same identity (keep your own field if you have one)
#     #     inv_id = payload["invoice_id"]
#     #     if move.x_pastel_doc_no != inv_id:
#     #         move.write({"x_pastel_doc_no": inv_id})
#     #
#     #     self._log("invoice", 1, 0, notes=f"UPSERT invoice_id={inv_id}")
#     #     _logger.info("Sage upsert OK: invoice_id=%s", inv_id)
#     #     return True
#     #
#     # @api.model
#     # def export_invoices_by_ids(self, ids):
#     #     results, exported, skipped = [], 0, 0
#     #     Move = self.env["account.move"].sudo()
#     #     for move in Move.browse(ids or []).exists():
#     #         if move.move_type not in ("out_invoice", "out_refund") or move.state != "posted":
#     #             results.append({"id": move.id, "name": move.name, "ok": False,
#     #                             "error": f"Unsupported or unposted move_type={move.move_type}"})
#     #             skipped += 1
#     #             continue
#     #         try:
#     #             self.export_invoice(move.id)
#     #             exported += 1
#     #             results.append({"id": move.id, "name": move.name, "ok": True,
#     #                             "invoice_id": str(move.id)})
#     #         except Exception as e:
#     #             skipped += 1
#     #             results.append({"id": move.id, "name": move.name, "ok": False, "error": str(e)})
#     #
#     #     errors = [r.get("error") for r in results if not r.get("ok") and r.get("error")]
#     #     return {
#     #         "exported": exported,
#     #         "skipped": skipped,
#     #         "total": exported + skipped,
#     #         "summary": {"exported": exported, "skipped": skipped, "total": exported + skipped},
#     #         "results": results,
#     #         "errors": errors,
#     #     }
#
#
#     # ---------------------
#     # EXPORT HELPERS
#     # ---------------------
#     @api.model
#     def _pastel_partner_code(self, partner):
#         return partner.x_pastel_code or partner.ref or str(partner.id)
#
#     @api.model
#     def _pastel_product_code(self, product):
#         tmpl = product.product_tmpl_id
#         return tmpl.x_pastel_item_code or product.default_code or tmpl.default_code or str(product.id)
#
#
#     # def _pastel_tax_code(self, line):
#     #     """
#     #     Resolve a Pastel tax code for a line.
#     #     Priority:
#     #       1) product template's x_pastel_tax_code if set
#     #       2) line.tax_ids[0].x_pastel_tax_code (or equivalent custom field on tax)
#     #       3) product template taxes_id[0].x_pastel_tax_code
#     #       4) fallback map by percentage -> Pastel code
#     #     Always returns a string code (e.g. "0", "1"), never False/None.
#     #     """
#     #     # 1) product-level override
#     #     tmpl = line.product_id.product_tmpl_id if line.product_id else False
#     #     code = (tmpl and getattr(tmpl, "x_pastel_tax_code", False)) or False
#     #     if code:
#     #         return str(code).strip()
#     #
#     #     # pick a tax from line or product template
#     #     taxes = line.tax_ids or (tmpl and tmpl.taxes_id) or self.env["account.tax"]
#     #     tax = taxes[:1]  # first applicable
#     #     tax = tax and tax[0] or False
#     #
#     #     # 2) custom code on the tax record?
#     #     if tax:
#     #         tax_code_on_tax = getattr(tax, "x_pastel_tax_code", False) or getattr(tax, "pastel_code", False)
#     #         if tax_code_on_tax:
#     #             return str(tax_code_on_tax).strip()
#     #
#     #         # 4) fallback map by percentage -> Pastel code (adjust to your setup)
#     #         # Example: SA VAT 15% -> Pastel "1", zero-rated/exempt -> "0"
#     #         try:
#     #             percent = int(round(float(tax.amount or 0)))
#     #         except Exception:
#     #             percent = 0
#     #
#     #         percent_to_pastel = {
#     #             0: "0",  # Exempt/Zero
#     #             14: "1",  # legacy
#     #             15: "1",  # standard VAT
#     #         }
#     #         return percent_to_pastel.get(percent, "0")
#     #
#     #     # nothing found
#     #     return "0"
#     #
#     # @api.model
#     # def _build_invoice_payload(self, move):
#     #     """Build JSON payload for Sage /invoices endpoint with correct lines."""
#     #     move.ensure_one()
#     #     if move.move_type not in ("out_invoice", "out_refund"):
#     #         raise UserError(_("Only customer invoices/refunds can be exported to Sage."))
#     #
#     #     cust_code = self._pastel_partner_code(move.partner_id)
#     #     if not cust_code:
#     #         raise UserError(_("Partner has no Sage code/ref: %s") % (move.partner_id.display_name,))
#     #
#     #     doc_no = move.x_pastel_doc_no or move.name or str(move.id)
#     #     payment_ref = move.payment_reference or move.ref or ""
#     #     # optional – your bridge currently reads invoice_payment_term_id (id/days). Keep name too if you like.
#     #     payment_terms_name = move.invoice_payment_term_id and move.invoice_payment_term_id.name or ""
#     #     payment_terms_id = move.invoice_payment_term_id.id if move.invoice_payment_term_id else None
#     #     currency = move.currency_id and move.currency_id.name or "ZAR"
#     #
#     #     delivery_date = getattr(move, "delivery_date", False)
#     #     if delivery_date:
#     #         delivery_date = delivery_date.isoformat()
#     #
#     #     lines = []
#     #     skipped_display = 0
#     #     skipped_nontab = 0
#     #     with_product = 0
#     #
#     #     for line in move.invoice_line_ids:
#     #         # Skip section/note lines only
#     #         if line.display_type in ("line_section", "line_note"):
#     #             skipped_display += 1
#     #             continue
#     #         # Skip lines not shown on the invoice tab (e.g., tax lines)
#     #         if getattr(line, "exclude_from_invoice_tab", False):
#     #             skipped_nontab += 1
#     #             continue
#     #
#     #         prod_code = self._pastel_product_code(line.product_id) if line.product_id else None
#     #         if prod_code:
#     #             with_product += 1
#     #
#     #         qty = float(line.quantity or 0.0)
#     #         price = float(line.price_unit or 0.0)
#     #         # texes = float (line.texes or 0.0)
#     #
#     #         # lines.append({
#     #         #     "product_code": prod_code,  # bridge → ItemCode (optional)
#     #         #     "name": line.name or (line.product_id and line.product_id.display_name) or "Line",
#     #         #     "quantity": qty,
#     #         #     "price_unit": price,
#     #         #     "taxes_id": line.product_id.product_tmpl_id.x_pastel_tax_code if line.product_id else None,
#     #         # })
#     #         lines.append({
#     #             "product_code": self._pastel_product_code(line.product_id) if line.product_id else None,
#     #             "label": line.name or (line.product_id and line.product_id.display_name) or "Line",
#     #             "quantity": float(line.quantity or 0.0),
#     #             "price_unit": float(line.price_unit or 0.0),
#     #             "subtotal_excl": float(line.price_subtotal or (line.quantity * line.price_unit)),
#     #             "tax_excl": float(line.price_subtotal or (line.quantity * line.price_unit)),
#     #             "total": float(line.price_subtotal or (line.quantity * line.price_unit)),  # adjust if you sum tax later
#     #             "tax_code": self._pastel_tax_code(line),  # <-- always a string like "0"/"1"
#     #         })
#     #
#     #     payload = {
#     #         "doc_no": doc_no,
#     #         "invoice_date": move.invoice_date and move.invoice_date.isoformat(),
#     #         "delivery_date": delivery_date,
#     #         "customer_code": cust_code,
#     #         "payment_reference": payment_ref,
#     #         "payment_terms": payment_terms_name,  # string (optional)
#     #         "invoice_payment_term_id": payment_terms_id,  # id (your bridge reads this)
#     #         "currency": currency,
#     #         "amount_total_excl": float(move.amount_untaxed or 0.0),
#     #         "tax_amount": float(move.amount_tax or 0.0),
#     #         "amount_total": float(move.amount_total or 0.0),
#     #         # out_invoice -> 3, out_refund -> 13 (Pastel History)
#     #         "document_type": 3 if move.move_type == "out_invoice" else 13,
#     #         "lines": lines,
#     #     }
#     #
#     #     _logger.info(
#     #         "Pastel export: invoice %s -> lines=%s (with_product=%s, display_skipped=%s, non_tab_skipped=%s)",
#     #         doc_no, len(lines), with_product, skipped_display, skipped_nontab
#     #     )
#     #     _logger.info("Pastel export payload for %s: %s", doc_no, json.dumps(payload, indent=2))
#     #     return payload
#
#     # at top of your model file (once)
#     import json
#
#
#
#     # -------------------------------------------------------------------
#     # Pastel tax-code resolver (always returns a string like "0" / "1")
#     # -------------------------------------------------------------------
#     def _pastel_tax_code(self, line):
#         """
#         Resolve a Pastel tax code for a line.
#         Priority:
#           1) product template's x_pastel_tax_code if set
#           2) line.tax_ids[0].x_pastel_tax_code (or similar custom field)
#           3) product template taxes_id[0].x_pastel_tax_code
#           4) fallback map by percentage -> Pastel code
#         Always returns a string code (e.g. "0", "1").
#         """
#         tmpl = line.product_id.product_tmpl_id if line.product_id else False
#
#         # (1) product-level override
#         code = (tmpl and getattr(tmpl, "x_pastel_tax_code", False)) or False
#         if code:
#             return str(code).strip()
#
#         # pick a tax from line or product template
#         taxes = line.tax_ids or (tmpl and tmpl.taxes_id) or self.env["account.tax"]
#         tax = taxes[:1]
#         tax = tax and tax[0] or False
#
#         # (2) custom code on the tax record?
#         if tax:
#             tax_code_on_tax = getattr(tax, "x_pastel_tax_code", False) or getattr(tax, "pastel_code", False)
#             if tax_code_on_tax:
#                 return str(tax_code_on_tax).strip()
#
#             # (4) fallback by percentage
#             try:
#                 percent = int(round(float(tax.amount or 0)))
#             except Exception:
#                 percent = 0
#
#             percent_to_pastel = {
#                 0: "0",  # Exempt/Zero
#                 14: "1",  # legacy VAT
#                 15: "1",  # standard VAT
#             }
#             return percent_to_pastel.get(percent, "0")
#
#         # nothing found
#         return "0"
#
#     # -------------------------------------------------------------------
#     # Coalesce duplicate lines before sending to the bridge
#     # -------------------------------------------------------------------
#     def _coalesce_lines_for_pastel(self, raw_lines):
#         """
#         Merge duplicate lines using a stable key:
#           (product_code, normalized name, rounded price_unit, tax_code)
#         Sums quantities; keeps first seen name/price/tax as canonical.
#         """
#
#         def _norm_name(s):
#             return (s or "").strip()
#
#         bucket = {}
#         for ln in raw_lines or []:
#             key = (
#                 (ln.get("product_code") or "").strip(),
#                 _norm_name(ln.get("label") or ln.get("name")),
#                 round(float(ln.get("price_unit") or 0.0), 4),
#                 str(ln.get("tax_code") if ln.get("tax_code") is not None else "0"),
#             )
#             if key not in bucket:
#                 bucket[key] = {
#                     "product_code": key[0] or None,
#                     "name": (ln.get("label") or ln.get("name") or "").strip(),
#                     "quantity": float(ln.get("quantity") or 0.0),
#                     "price_unit": key[2],
#                     "tax_code": key[3],
#                 }
#             else:
#                 bucket[key]["quantity"] += float(ln.get("quantity") or 0.0)
#
#         # Optional: drop obvious “Sage import” placeholders
#         out = []
#         for v in bucket.values():
#             n = (v.get("name") or "").lower()
#             p = (v.get("product_code") or "").lower()
#             if n == "sage import" and p == "sage import":
#                 continue
#             out.append(v)
#
#         return out
#
#     # -------------------------------------------------------------------
#     # Build payload (with deduped lines) for /invoices
#     # -------------------------------------------------------------------
#     @api.model
#     def _build_invoice_payload(self, move):
#         """Build JSON payload for Sage /invoices endpoint with correct lines."""
#         move.ensure_one()
#         if move.move_type not in ("out_invoice", "out_refund"):
#             raise UserError(_("Only customer invoices/refunds can be exported to Sage."))
#
#         # customer code
#         cust_code = self._pastel_partner_code(move.partner_id)
#         if not cust_code:
#             raise UserError(_("Partner has no Sage code/ref: %s") % (move.partner_id.display_name,))
#
#         # header basics
#         doc_no = move.x_pastel_doc_no or move.name or str(move.id)
#         payment_ref = move.payment_reference or move.ref or ""
#
#         # keep both: readable name and the id (bridge may read the id)
#         payment_terms_name = (move.invoice_payment_term_id and move.invoice_payment_term_id.name) or ""
#         payment_terms_id = move.invoice_payment_term_id.id if move.invoice_payment_term_id else None
#
#         currency = (move.currency_id and move.currency_id.name) or "ZAR"
#
#         # optional delivery date (use invoice_date as fallback so the bridge always sees a date)
#         delivery_date = getattr(move, "delivery_date", False)
#         if delivery_date:
#             delivery_date = delivery_date.isoformat()
#         else:
#             delivery_date = move.invoice_date and move.invoice_date.isoformat()
#
#         lines = []
#         skipped_display = 0
#         skipped_nontab = 0
#         with_product = 0
#
#         for line in move.invoice_line_ids:
#             # skip section/note rows only
#             if line.display_type in ("line_section", "line_note"):
#                 skipped_display += 1
#                 continue
#             # skip lines that are not shown on invoice tab (e.g. automatic tax lines)
#             if getattr(line, "exclude_from_invoice_tab", False):
#                 skipped_nontab += 1
#                 continue
#
#             prod_code = self._pastel_product_code(line.product_id) if line.product_id else None
#             if prod_code:
#                 with_product += 1
#
#             qty = float(line.quantity or 0.0)
#             price = float(line.price_unit or 0.0)
#
#             # Build line dict (bridge maps these to HistoryLines)
#             lines.append({
#                 # bridge accepts product_code and label/name
#                 "product_code": prod_code,
#                 "label": line.name or (line.product_id and line.product_id.display_name) or "Line",
#                 "quantity": qty,
#                 "price_unit": price,
#                 # simple exclusive amounts; bridge totals header
#                 "subtotal_excl": float(line.price_subtotal or (qty * price)),
#                 "tax_excl": float(line.price_subtotal or (qty * price)),
#                 "total": float(line.price_subtotal or (qty * price)),
#                 # must be a primitive string code
#                 "tax_code": self._pastel_tax_code(line),
#             })
#
#         # Deduplicate identical lines (sum quantities)
#         lines = self._coalesce_lines_for_pastel(lines)
#
#         # Compose payload (header totals from Odoo; the bridge will also compute)
#         payload = {
#             "doc_no": doc_no,
#             "invoice_date": move.invoice_date and move.invoice_date.isoformat(),
#             "delivery_date": delivery_date,  # guaranteed date string if invoice_date exists
#             "customer_code": cust_code,
#             "payment_reference": payment_ref,
#             "payment_terms": payment_terms_name,  # readable string
#             "invoice_payment_term_id": payment_terms_id,  # numeric id (bridge can map to Terms)
#             "currency": currency,
#             "amount_total_excl": float(move.amount_untaxed or 0.0),
#             "tax_amount": float(move.amount_tax or 0.0),
#             "amount_total": float(move.amount_total or 0.0),
#             # Pastel History: out_invoice -> 3, out_refund -> 13
#             "document_type": 3 if move.move_type == "out_invoice" else 13,
#             "lines": lines,
#         }
#
#         _logger.info(
#             "Pastel export: invoice %s -> lines=%s (with_product=%s, display_skipped=%s, non_tab_skipped=%s)",
#             doc_no, len(lines), with_product, skipped_display, skipped_nontab
#         )
#         _logger.info("Pastel export payload for %s: %s", doc_no, json.dumps(payload, indent=2))
#         return payload
#
#     last_sync_at = fields.Datetime(string="Last Sync At")
#
#
#
#     def _push_invoice(self, move):
#         """
#         Idempotent push:
#           - If invoice exists in Sage -> PUT (replace header+lines)
#           - Else -> POST (create)
#           - Race-safe fallback: 404 after PUT => POST; 409 after POST => PUT
#         Also coalesces duplicate lines via _build_invoice_payload.
#         """
#         base, key = self._conf()  # your existing conf (bridge URL + API key)
#
#         payload = self._build_invoice_payload(move)  # your function (already dedupes lines)
#         doc_no = payload.get("doc_no")
#         doc_type = int(payload.get("document_type") or 3)
#         if not doc_no:
#             raise UserError(_("Missing doc_no for %s") % (move.display_name,))
#
#         headers = {
#             "x-api-key": key,
#             "Content-Type": "application/json",
#             # idempotency guard per invoice:
#             "Idempotency-Key": f"odoo-{move.id}-{doc_no}-{doc_type}",
#         }
#         put_url = f"{base.rstrip('/')}/invoices/{quote(doc_no, safe='')}"
#         post_url = f"{base.rstrip('/')}/invoices"
#
#         # Decide existence: prefer stored Sage number; otherwise ask bridge /exists
#         if move.x_pastel_doc_no:
#             exists = True
#         else:
#             exists = self._bridge_invoice_exists(base, key, doc_no, doc_type)
#
#         if exists:
#             resp = requests.put(put_url, json=payload, headers=headers, timeout=40)
#             if resp.status_code == 404:  # deleted after we checked
#                 resp = requests.post(post_url, json=payload, headers=headers, timeout=40)
#                 if resp.status_code == 409:  # created concurrently
#                     resp = requests.put(put_url, json=payload, headers=headers, timeout=40)
#             action = "update"
#         else:
#             resp = requests.post(post_url, json=payload, headers=headers, timeout=40)
#             if resp.status_code == 409:  # already exists after all
#                 resp = requests.put(put_url, json=payload, headers=headers, timeout=40)
#             action = "create"
#
#         if not (200 <= resp.status_code < 300):
#             raise UserError(_("Bridge error %s: %s") % (resp.status_code, resp.text))
#
#         try:
#             data = resp.json() if resp.text else {}
#         except Exception:
#             data = {}
#
#         returned_no = data.get("doc_no") or doc_no
#         if move.x_pastel_doc_no != returned_no:
#             move.write({"x_pastel_doc_no": returned_no})
#
#         # optional stamp so sync can be incremental
#         if not hasattr(move, "x_pastel_synced_at"):
#             # add a field in your model if you want, otherwise skip
#             pass
#         else:
#             move.write({"x_pastel_synced_at": fields.Datetime.now()})
#
#         self._log("invoice", 1, 0, notes=f"{action.upper()} {returned_no}")
#         return action
#     # -------------------------------------------------------------------
#     # Export one invoice with deterministic "update if exists, create if not"
#     # -------------------------------------------------------------------
#
#     @api.model
#     def export_invoice(self, move_id):
#         base, key = self._conf()  # e.g. http://localhost:8787 , "superlongrandomtoken"
#
#         Move = self.env["account.move"].sudo()
#         move = Move.browse(move_id)
#         if not move.exists():
#             raise UserError(_("Invoice not found (id=%s).") % move_id)
#         if move.move_type not in ("out_invoice", "out_refund") or move.state != "posted":
#             raise UserError(_("Only posted customer invoices/credit notes can be exported."))
#
#         payload = self._build_invoice_payload(move)  # uses your coalescing logic
#         doc_no   = payload.get("doc_no")
#         doc_type = int(payload.get("document_type") or 3)
#         if not doc_no:
#             raise UserError(_("Missing doc_no in payload."))
#
#         headers = {
#             "x-api-key": key,
#             "Content-Type": "application/json",
#             # optional idempotency key per invoice+write
#             "Idempotency-Key": f"odoo-{move.id}-{doc_no}-{doc_type}"
#         }
#         put_url  = f"{base.rstrip('/')}/invoices/{quote(doc_no, safe='')}"
#         post_url = f"{base.rstrip('/')}/invoices"
#
#         # Decide path:
#         #  - if we've already stored a Sage number -> definitely UPDATE (PUT)
#         #  - else ask the bridge once whether (doc_no, doc_type) exists
#         try:
#             if move.x_pastel_doc_no:
#                 exists = True
#             else:
#                 exists_url = f"{base.rstrip('/')}/invoices/exists"
#                 ex = requests.get(
#                     exists_url,
#                     params={"doc_no": doc_no, "doc_type": doc_type},
#                     headers=headers,
#                     timeout=15
#                 )
#                 ex.raise_for_status()
#                 exists = bool(ex.json().get("exists"))
#         except Exception as e:
#             raise UserError(_("Bridge exists-check failed: %s") % e)
#
#         # Execute chosen path with race-safe fallbacks
#         action = None
#         try:
#             if exists:
#                 # UPDATE
#                 resp = requests.put(put_url, json=payload, headers=headers, timeout=30)
#                 if resp.status_code == 404:
#                     # race (deleted between check and put) -> CREATE
#                     resp = requests.post(post_url, json=payload, headers=headers, timeout=30)
#                     if resp.status_code == 409:
#                         # created concurrently -> UPDATE again
#                         resp = requests.put(put_url, json=payload, headers=headers, timeout=30)
#                 action = "Updated"
#             else:
#                 # CREATE
#                 resp = requests.post(post_url, json=payload, headers=headers, timeout=30)
#                 if resp.status_code == 409:
#                     # existed already (race) -> UPDATE
#                     resp = requests.put(put_url, json=payload, headers=headers, timeout=30)
#                 action = "Created"
#         except requests.RequestException as e:
#             raise UserError(_("Bridge request failed: %s") % e)
#
#         if not (200 <= resp.status_code < 300):
#             raise UserError(_("Bridge error %s: %s") % (resp.status_code, resp.text))
#
#         # Persist the authoritative doc_no that Sage/bridge returns (prevents new docs later)
#         try:
#             data = resp.json() if resp.text else {}
#         except Exception:
#             data = {}
#         returned_no = data.get("doc_no") or doc_no
#         if move.x_pastel_doc_no != returned_no:
#             move.write({"x_pastel_doc_no": returned_no})
#
#         self._log("invoice", 1, 0, notes=f"{action} invoice {returned_no}")
#         _logger.info("Sage upsert OK: %s %s", action, json.dumps(payload, indent=2))
#         return True
#
#     # -------------------------------------------------------------------
#     # Batch export with retry on transient errors (no duplicates)
#     # -------------------------------------------------------------------
#     @api.model
#     def export_invoices_by_ids(self, ids):
#         results, exported, skipped = [], 0, 0
#         Move = self.env["account.move"].sudo()
#         moves = Move.browse(ids or []).exists()
#
#         for move in moves:
#             if move.move_type not in ("out_invoice", "out_refund") or move.state != "posted":
#                 results.append({
#                     "id": move.id, "name": move.name, "ok": False,
#                     "error": f"Unsupported or unposted move_type={move.move_type}"
#                 })
#                 skipped += 1
#                 continue
#
#             attempts, max_attempts, last_err = 0, 2, None
#             while attempts < max_attempts:
#                 attempts += 1
#                 try:
#                     self.export_invoice(move.id)
#                     exported += 1
#                     results.append({
#                         "id": move.id,
#                         "name": move.name,
#                         "ok": True,
#                         "doc_no": move.x_pastel_doc_no or move.name,
#                         "attempts": attempts,
#                     })
#                     break
#                 except Exception as e:
#                     last_err = str(e)
#                     transient = any(tok in last_err.lower() for tok in [
#                         "timeout", "temporarily", "connection", "502", "503", "504"
#                     ])
#                     if attempts < max_attempts and transient:
#                         time.sleep(1.0)
#                         continue
#                     skipped += 1
#                     results.append({
#                         "id": move.id, "name": move.name, "ok": False,
#                         "error": last_err, "attempts": attempts,
#                     })
#                     break
#
#         errors = [r.get("error") for r in results if not r.get("ok") and r.get("error")]
#         return {
#             "exported": exported,
#             "skipped": skipped,
#             "total": exported + skipped,
#             "summary": {"exported": exported, "skipped": skipped, "total": exported + skipped},
#             "results": results,
#             "errors": errors,
#         }
#
#
#     @api.model
#     def export_invoice(self, move_id):
#         base, key = self._conf()
#         Move = self.env["account.move"].sudo()
#         move = Move.browse(move_id)
#         if not move.exists():
#             raise UserError(_("Invoice not found (id=%s).") % move_id)
#
#         payload = self._build_invoice_payload(move)
#
#         # create vs update
#         if move.x_pastel_doc_no:
#             self._req("PUT", f"/invoices/{payload['doc_no']}", key, base, json=payload)
#         else:
#             res = self._req("POST", "/invoices", key, base, json=payload)
#
#             # if bridge echoes doc_no back, persist it
#             if isinstance(res, dict) and res.get("doc_no"):
#                 move.write({"x_pastel_doc_no": res["doc_no"]})
#
#         self._log("invoice", 1, 0, notes=f"Exported invoice {payload['doc_no']}")
#
#         print("EXPORT PAYLOAD:", json.dumps(payload, indent=2))
#         return True
#
#     @api.model
#     def export_invoices_by_ids(self, ids):
#         exported = skipped = 0
#         errors = []
#         for mid in ids or []:
#             try:
#                 self.export_invoice(mid)
#                 exported += 1
#             except Exception as e:
#                 skipped += 1
#                 errors.append(f"id={mid}: {e}")
#         return {"exported": exported, "skipped": skipped, "errors": errors}
#
#
#
#
