"""Import masters and export invoices/receipts through sage.client."""

import json
import logging

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SageSync(models.AbstractModel):
    """Public API used by wizards, crons, and pastel_batch_payment."""

    _name = "sage.sync"
    _description = "Sage Sync Service"

    def _client(self):
        return self.env["sage.client"]

    def _backend(self, company=None):
        return self.env["sage.backend"]._for_company(company or self.env.company)

    def import_masters(self, backend=None, kinds=None):
        """Pull customers/suppliers/products/invoices page by page."""
        backend = backend or self._backend()
        kinds = kinds or []
        if not kinds:
            if backend.import_customers:
                kinds.append("customers")
            if backend.import_suppliers:
                kinds.append("suppliers")
            if backend.import_products:
                kinds.append("products")
            if backend.import_invoices:
                kinds.append("invoices")
        result = {}
        ctx = dict(self.env.context, sage_sync_origin=True)
        sync = self.with_context(ctx)
        mapping = {
            "customers": ("/v1/customers", "last_customer_cursor", "last_customer_since", sync._upsert_customer),
            "suppliers": ("/v1/suppliers", "last_supplier_cursor", "last_supplier_since", sync._upsert_supplier),
            "products": ("/v1/products", "last_product_cursor", "last_product_since", sync._upsert_product_row),
            "invoices": ("/v1/invoices", "last_invoice_cursor", "last_invoice_since", sync._upsert_invoice_row),
        }
        for kind in kinds:
            path, cursor_f, since_f, handler = mapping[kind]
            created = updated = skipped = 0
            cursor = False
            since = getattr(backend, since_f)
            since_s = since.isoformat() if since else None
            while True:
                items, next_cursor, has_more = self._client().get_page(
                    backend, path, since=since_s, cursor=cursor or None, limit=200,
                )
                for row in items:
                    status = handler(backend, row)
                    if status == "created":
                        created += 1
                    elif status == "updated":
                        updated += 1
                    else:
                        skipped += 1
                if not has_more:
                    break
                cursor = next_cursor
            vals = {cursor_f: False, since_f: fields.Date.context_today(self)}
            backend.write(vals)
            result[kind] = {"created": created, "updated": updated, "skipped": skipped}
            self.env["sage.sync.log"].sudo().create({
                "backend_id": backend.id,
                "method": "IMPORT",
                "path": path,
                "ok": True,
                "request_body": kind,
                "response_body": json.dumps(result[kind]),
            })
        return result

    def _partner_by_code(self, code, supplier=False):
        Partner = self.env["res.partner"].sudo()
        domain = [("x_pastel_code", "=", code)]
        rec = Partner.search(domain, limit=1)
        return rec

    def _upsert_customer(self, backend, row):
        code = (row.get("code") or "").strip()
        if not code:
            return "skipped"
        partner = self._partner_by_code(code)
        vals = {
            "name": row.get("name") or code,
            "x_pastel_code": code,
            "sage_code": code,
            "phone": row.get("phone") or False,
            "email": row.get("email") or False,
            "x_pastel_tax_code": row.get("tax_code") or False,
            "x_pastel_credit_limit": row.get("credit_limit") or 0,
            "x_pastel_balance": row.get("balance") or 0,
            "x_pastel_currency_code": row.get("currency_code") or False,
            "customer_rank": 1,
            "company_id": backend.company_id.id,
        }
        if partner:
            vals.pop("x_pastel_code", None)
            vals.pop("sage_code", None)
            partner.with_context(sage_sync_origin=True).write(vals)
            return "updated"
        Partner = self.env["res.partner"].sudo().with_context(sage_sync_origin=True)
        Partner.create(vals)
        return "created"

    def _upsert_supplier(self, backend, row):
        code = (row.get("code") or "").strip()
        if not code:
            return "skipped"
        partner = self._partner_by_code(code)
        vals = {
            "name": row.get("name") or code,
            "x_pastel_code": code,
            "sage_code": code,
            "phone": row.get("phone") or False,
            "email": row.get("email") or False,
            "x_pastel_tax_code": row.get("tax_code") or False,
            "x_pastel_credit_limit": row.get("credit_limit") or 0,
            "x_pastel_balance": row.get("balance") or 0,
            "supplier_rank": 1,
            "company_id": backend.company_id.id,
        }
        if partner:
            vals.pop("x_pastel_code", None)
            vals.pop("sage_code", None)
            partner.with_context(sage_sync_origin=True).write(vals)
            return "updated"
        self.env["res.partner"].sudo().with_context(sage_sync_origin=True).create(vals)
        return "created"

    def _upsert_product_row(self, backend, row):
        code = (row.get("code") or "").strip()
        if not code:
            return "skipped"
        Product = self.env["product.template"].sudo()
        product = Product.search([("x_pastel_item_code", "=", code)], limit=1)
        vals = {
            "name": row.get("name") or code,
            "x_pastel_item_code": code,
            "sage_code": code,
            "default_code": code,
            "x_pastel_tax_code": row.get("tax_code") or False,
            "company_id": backend.company_id.id,
        }
        if product:
            vals.pop("x_pastel_item_code", None)
            vals.pop("sage_code", None)
            vals.pop("default_code", None)
            product.with_context(sage_sync_origin=True).write(vals)
            return "updated"
        Product.with_context(sage_sync_origin=True).create(vals)
        return "created"

    def _upsert_invoice_row(self, backend, row):
        doc_no = (row.get("doc_no") or "").strip()
        if not doc_no:
            return "skipped"
        Move = self.env["account.move"].sudo()
        existing = Move.search([("x_pastel_doc_no", "=", doc_no)], limit=1)
        if existing:
            return "skipped"
        cust = (row.get("customer_code") or "").strip()
        partner = self._partner_by_code(cust) if cust else False
        if not partner:
            return "skipped"
        lines = []
        Product = self.env["product.template"].sudo()
        for ln in row.get("lines") or []:
            pcode = (ln.get("product_code") or "").strip()
            product = Product.search([("x_pastel_item_code", "=", pcode)], limit=1) if pcode else False
            if pcode and not product:
                return "skipped"
            lines.append((0, 0, {
                "name": ln.get("name") or pcode or "Line",
                "product_id": product.product_variant_id.id if product else False,
                "quantity": ln.get("quantity") or 1.0,
                "price_unit": ln.get("price_unit") or 0.0,
            }))
        if not lines:
            lines = [(0, 0, {"name": "Sage import", "quantity": 1, "price_unit": row.get("amount_total") or 0})]
        doc_type = int(row.get("document_type") or 3)
        move_type = "out_refund" if doc_type == 13 else "out_invoice"
        Move.with_context(sage_sync_origin=True).create({
            "move_type": move_type,
            "partner_id": partner.id,
            "invoice_date": row.get("invoice_date") or False,
            "x_pastel_doc_no": doc_no,
            "sage_doc_no": doc_no,
            "invoice_line_ids": lines,
            "company_id": backend.company_id.id,
        })
        return "created"

    def _sage_tax_code(self, backend, line):
        tax = line.tax_ids[:1]
        if not tax:
            raise UserError(_("Invoice line %s has no tax. Map taxes before export.") % (line.display_name,))
        mapping = self.env["sage.mapping.tax"].search([
            ("backend_id", "=", backend.id),
            ("tax_id", "=", tax.id),
        ], limit=1)
        if mapping:
            return mapping.sage_tax_code
        if tax.x_pastel_tax_code if hasattr(tax, "x_pastel_tax_code") else False:
            return tax.x_pastel_tax_code
        raise UserError(_(
            "No Sage tax mapping for %s. Configure Sage Connector → Tax Mappings."
        ) % tax.display_name)

    def _sage_journal_code(self, backend, journal):
        if not journal:
            return False
        mapping = self.env["sage.mapping.journal"].search([
            ("backend_id", "=", backend.id),
            ("journal_id", "=", journal.id),
        ], limit=1)
        return mapping.sage_journal_code if mapping else journal.code

    def _partner_code(self, partner):
        code = (partner.x_pastel_code or partner.sage_code or partner.ref or "").strip()
        if code and len(code) > 6:
            raise UserError(_(
                "Partner %s has Sage customer code %r which is longer than Pastel's "
                "6-character limit. Set a short code on the contact Sage tab "
                "(must match an existing Pastel customer), then export again."
            ) % (partner.display_name, code))
        return code

    def _product_code(self, product):
        if not product:
            return False
        tmpl = product.product_tmpl_id
        return (tmpl.x_pastel_item_code or tmpl.sage_code or product.default_code or "").strip()

    def _pastel_doc_no(self, move):
        """Pastel HistoryHeader.DocumentNumber is CHAR(8) and rejects '/'."""
        existing = (move.x_pastel_doc_no or move.sage_doc_no or "").strip()
        if existing and len(existing) <= 8 and "/" not in existing:
            return existing
        # Drop invalid leftovers (e.g. Odoo names like INV/2026/00002).
        if existing and (move.x_pastel_doc_no or move.sage_doc_no):
            move.with_context(sage_sync_origin=True).write({
                "x_pastel_doc_no": False,
                "sage_doc_no": False,
            })
        return ("IN%06d" % (move.id % 1000000))[:8]

    def _build_invoice_payload(self, move, backend):
        if move.move_type not in ("out_invoice", "out_refund") or move.state != "posted":
            raise UserError(_("Only posted customer invoices/credit notes can be exported."))
        cust = self._partner_code(move.partner_id)
        if not cust:
            raise UserError(_("Partner %s has no Sage customer code.") % move.partner_id.display_name)
        lines = []
        for line in move.invoice_line_ids:
            if line.display_type in ("line_section", "line_note"):
                continue
            pcode = self._product_code(line.product_id) if line.product_id else False
            if line.product_id and not pcode:
                raise UserError(_("Product %s has no Sage item code.") % line.product_id.display_name)
            lines.append({
                "product_code": pcode,
                "name": line.name or (line.product_id and line.product_id.display_name) or "Line",
                "quantity": float(line.quantity or 0.0),
                "price_unit": float(line.price_unit or 0.0),
                "tax_code": self._sage_tax_code(backend, line),
            })
        if not lines:
            raise UserError(_("Invoice %s has no exportable lines.") % move.display_name)
        doc_no = self._pastel_doc_no(move)
        return {
            "doc_no": doc_no,
            "invoice_date": move.invoice_date and move.invoice_date.isoformat(),
            "delivery_date": (move.invoice_date_due or move.invoice_date) and (move.invoice_date_due or move.invoice_date).isoformat(),
            "customer_code": cust,
            "payment_reference": move.payment_reference or move.name,
            "currency": move.currency_id.name or "ZAR",
            "document_type": 13 if move.move_type == "out_refund" else 3,
            "lines": lines,
        }

    def import_selected(self, backend, kind, rows):
        """Import only the previewed/edited rows (no full re-pull)."""
        backend = backend or self._backend()
        handlers = {
            "customers": self._upsert_customer,
            "suppliers": self._upsert_supplier,
            "products": self._upsert_product_row,
            "invoices": self._upsert_invoice_row,
        }
        handler = handlers.get(kind)
        if not handler:
            raise UserError(_("Unknown import type %s") % kind)
        created = updated = skipped = failed = 0
        errors = []
        ctx = dict(self.env.context, sage_sync_origin=True)
        sync = self.with_context(ctx)
        handler = getattr(sync, handler.__name__)
        for row in rows or []:
            try:
                status = handler(backend, row)
                if status == "created":
                    created += 1
                elif status == "updated":
                    updated += 1
                else:
                    skipped += 1
            except Exception as exc:
                failed += 1
                errors.append("%s: %s" % (row.get("code") or row.get("doc_no") or "?", exc))
        result = {
            "kind": kind,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "errors": errors[:20],
        }
        self.env["sage.sync.log"].sudo().create({
            "backend_id": backend.id,
            "method": "IMPORT",
            "path": "/v1/%s" % kind,
            "ok": not failed,
            "request_body": json.dumps({"count": len(rows or []), "kind": kind}),
            "response_body": json.dumps(result, default=str),
            "error": "\n".join(errors[:5]) if errors else False,
        })
        return result

    def export_selected(self, backend, kind, rows):
        """Export selected Odoo records, using edited preview payloads."""
        backend = backend or self._backend()
        exported = skipped = failed = 0
        errors = []
        for row in rows or []:
            try:
                res_id = int(row.get("odoo_res_id") or 0)
                if kind in ("customers", "suppliers"):
                    partner = self.env["res.partner"].browse(res_id)
                    if not partner.exists():
                        skipped += 1
                        continue
                    if kind == "suppliers":
                        skipped += 1
                        errors.append("%s: supplier upsert is not supported by this Sage adapter" % (row.get("code") or partner.display_name))
                        continue
                    extra = {
                        "name": row.get("name") or partner.name,
                        "phone": row.get("phone"),
                        "email": row.get("email"),
                        "tax_code": row.get("tax_code"),
                        "credit_limit": row.get("credit_limit"),
                    }
                    partner.with_context(sage_sync_origin=True).write({
                        "name": extra["name"] or partner.name,
                        "phone": extra.get("phone") or False,
                        "email": extra.get("email") or False,
                        "x_pastel_tax_code": extra.get("tax_code") or False,
                        "x_pastel_credit_limit": extra.get("credit_limit") or 0,
                    })
                    result = self.upsert_partner(partner, force=True, extra=extra)
                    if result.get("skipped"):
                        skipped += 1
                    else:
                        exported += 1
                elif kind == "products":
                    product = self.env["product.template"].browse(res_id)
                    if not product.exists():
                        skipped += 1
                        continue
                    extra = {"name": row.get("name") or product.name, "tax_code": row.get("tax_code")}
                    product.with_context(sage_sync_origin=True).write({
                        "name": extra["name"] or product.name,
                        "x_pastel_tax_code": extra.get("tax_code") or False,
                    })
                    result = self.upsert_product(product, force=True, extra=extra)
                    if result.get("skipped"):
                        skipped += 1
                    else:
                        exported += 1
                elif kind == "invoices":
                    move = self.env["account.move"].browse(res_id)
                    if not move.exists():
                        skipped += 1
                        continue
                    try:
                        payload = self._build_invoice_payload(move, backend)
                    except UserError:
                        payload = {}
                    payload.update({k: v for k, v in row.items() if k not in ("odoo_res_id", "odoo_res_model")})
                    self.export_invoice(move, payload=payload)
                    exported += 1
                else:
                    raise UserError(_("Unknown export type %s") % kind)
            except Exception as exc:
                failed += 1
                errors.append("%s: %s" % (row.get("code") or row.get("doc_no") or res_id, exc))
        result = {
            "kind": kind,
            "exported": exported,
            "skipped": skipped,
            "failed": failed,
            "errors": errors[:20],
        }
        self.env["sage.sync.log"].sudo().create({
            "backend_id": backend.id,
            "method": "EXPORT",
            "path": "/v1/%s" % kind,
            "ok": not failed,
            "request_body": json.dumps({"count": len(rows or []), "kind": kind}),
            "response_body": json.dumps(result, default=str),
            "error": "\n".join(errors[:5]) if errors else False,
        })
        return result

    def export_invoice(self, move, job=None, payload=None):
        """Export one posted invoice. Persist Sage's returned doc_no."""
        move.ensure_one()
        backend = self._backend(move.company_id)
        payload = payload or self._build_invoice_payload(move, backend)
        idem = "odoo-move-%s-%s" % (move.id, move.write_date)
        # Always ask Pastel — a local sage_doc_no may be leftover from a failed write.
        check = self._client().request(
            backend, "GET", "/v1/invoices/exists",
            params={"doc_no": payload["doc_no"], "doc_type": payload["document_type"]},
            job=job,
        )
        exists = bool(check.get("exists_strict") or check.get("exists"))
        result = None
        if exists:
            try:
                result = self._client().request(
                    backend, "PUT", "/v1/invoices/%s" % payload["doc_no"],
                    json_body=payload, idempotency_key=idem, job=job,
                )
            except UserError as exc:
                if "404" not in str(exc):
                    raise
                exists = False
        if not exists:
            try:
                result = self._client().request(
                    backend, "POST", "/v1/invoices",
                    json_body=payload, idempotency_key=idem, job=job,
                )
            except UserError as exc:
                if "409" not in str(exc):
                    raise
                result = self._client().request(
                    backend, "PUT", "/v1/invoices/%s" % payload["doc_no"],
                    json_body=payload, idempotency_key=idem, job=job,
                )
        sage_no = (result or {}).get("doc_no") or payload["doc_no"]
        move.with_context(sage_sync_origin=True).write({
            "x_pastel_doc_no": sage_no,
            "sage_doc_no": sage_no,
        })
        return result

    def export_receipt_batch(self, batch, job=None):
        """Export invoices first, then the receipt batch. Never re-posts invoices on receipt failure."""
        batch.ensure_one()
        backend = self._backend(batch.company_id)
        if not backend.capability("post_receipt_batch"):
            raise UserError(_("This Sage adapter does not support receipt batches."))
        for line in batch.line_ids:
            invoice = line.move_id
            if not invoice:
                continue
            if invoice.x_pastel_doc_no or invoice.sage_doc_no:
                continue
            self.export_invoice(invoice, job=job)
        journal_code = self._sage_journal_code(backend, batch.journal_id)
        lines = []
        for line in batch.line_ids:
            invoice = line.move_id
            partner = invoice.partner_id if invoice else line.partner_id
            code = self._partner_code(partner) if partner else ""
            if not code:
                raise UserError(_("Missing Sage partner code on batch line %s.") % line.id)
            doc_no = False
            if invoice:
                doc_no = invoice.x_pastel_doc_no or invoice.sage_doc_no
            lines.append({
                "partner_code": code,
                "invoice_doc_no": doc_no or None,
                "amount": float(line.amount or 0.0),
                "reference": line.communication or batch.name,
                "currency_code": batch.currency_id.name or "ZAR",
                "allocate": bool(doc_no),
            })
        payload = {
            "batch_ref": batch.name,
            "payment_date": str(batch.payment_date),
            "partner_type": batch.partner_type or "customer",
            "journal_code": journal_code,
            "currency_code": batch.currency_id.name or "ZAR",
            "lines": lines,
        }
        idem = "odoo-batch-%s-%s" % (batch.id, batch.write_date)
        result = self._client().request(
            backend, "POST", "/v1/payments/batch",
            json_body=payload, idempotency_key=idem, job=job,
        )
        sage_ref = (result or {}).get("batch_id") or batch.name
        batch.write({"exported_ref": sage_ref})
        return result

    def upsert_partner(self, partner, force=False, extra=None):
        backend = self._backend(partner.company_id or self.env.company)
        if not backend.push_masters and not force:
            return {"skipped": True}
        code = self._partner_code(partner)
        if not code:
            raise UserError(_("Partner %s has no Sage code.") % partner.display_name)
        extra = extra or {}
        return self._client().request(
            backend, "PUT", "/v1/customers/%s" % code,
            json_body={
                "name": extra.get("name") or partner.name,
                "tax_code": extra.get("tax_code") if extra.get("tax_code") is not None else partner.x_pastel_tax_code,
                "currency_code": extra.get("currency_code") or partner.x_pastel_currency_code,
                "credit_limit": extra.get("credit_limit") if extra.get("credit_limit") is not None else partner.x_pastel_credit_limit,
            },
        )

    def upsert_product(self, product, force=False, extra=None):
        backend = self._backend(product.company_id or self.env.company)
        if not backend.push_masters and not force:
            return {"skipped": True}
        code = product.x_pastel_item_code or product.sage_code or product.default_code
        if not code:
            raise UserError(_("Product %s has no Sage item code.") % product.display_name)
        extra = extra or {}
        return self._client().request(
            backend, "PUT", "/v1/products/%s" % code,
            json_body={
                "name": extra.get("name") or product.name,
                "tax_code": extra.get("tax_code") if extra.get("tax_code") is not None else product.x_pastel_tax_code,
            },
        )
