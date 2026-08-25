"""Preview, select, edit, then import from Sage or export to Sage."""

import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError

PREVIEW_LIMIT = 500
KIND_PATH = {
    "customers": "/v1/customers",
    "suppliers": "/v1/suppliers",
    "products": "/v1/products",
    "invoices": "/v1/invoices",
}


class SageTransferWizard(models.TransientModel):
    """Step wizard: setup, editable preview, confirm, transfer."""

    _name = "sage.transfer.wizard"
    _description = "Sage Transfer Wizard"

    name = fields.Char(compute="_compute_name", store=True)

    backend_id = fields.Many2one(
        "sage.backend",
        required=True,
        default=lambda s: s.env["sage.backend"].search(
            [("company_id", "=", s.env.company.id)], limit=1
        ),
    )
    direction = fields.Selection(
        [("import", "Import from Sage"), ("export", "Export to Sage")],
        required=True,
        default="import",
    )
    data_type = fields.Selection(
        [
            ("customers", "Customers"),
            ("suppliers", "Suppliers"),
            ("products", "Inventory"),
            ("invoices", "Invoices"),
        ],
        required=True,
        default="customers",
        string="Data",
    )
    search = fields.Char(string="Search")
    date_from = fields.Date(string="From date")
    state = fields.Selection(
        [
            ("setup", "Setup"),
            ("preview", "Preview"),
            ("confirm", "Confirm"),
            ("done", "Done"),
        ],
        default="setup",
        required=True,
    )
    truncated = fields.Boolean(readonly=True)
    preview_note = fields.Char(readonly=True)
    line_ids = fields.One2many("sage.transfer.line", "wizard_id")
    line_count = fields.Integer(compute="_compute_counts")
    selected_count = fields.Integer(compute="_compute_counts")
    new_count = fields.Integer(compute="_compute_counts")
    update_count = fields.Integer(compute="_compute_counts")
    skip_count = fields.Integer(compute="_compute_counts")
    selected_line_ids = fields.Many2many(
        "sage.transfer.line",
        compute="_compute_counts",
        string="Selected rows",
    )
    result_text = fields.Text(readonly=True)

    is_partner_type = fields.Boolean(compute="_compute_flags")
    is_product_type = fields.Boolean(compute="_compute_flags")
    is_invoice_type = fields.Boolean(compute="_compute_flags")
    is_import = fields.Boolean(compute="_compute_flags")
    step_hint = fields.Char(compute="_compute_step_hint")

    @api.depends("direction", "data_type", "backend_id", "state")
    def _compute_name(self):
        labels = dict(self._fields["data_type"].selection)
        dirs = dict(self._fields["direction"].selection)
        for rec in self:
            data = labels.get(rec.data_type) or _("Data")
            direction = dirs.get(rec.direction) or _("Transfer")
            backend = rec.backend_id.name or _("Sage")
            rec.name = _("%(direction)s · %(data)s · %(backend)s") % {
                "direction": direction,
                "data": data,
                "backend": backend,
            }

    @api.depends("state", "direction", "selected_count", "line_count")
    def _compute_step_hint(self):
        for rec in self:
            if rec.state == "setup":
                rec.step_hint = _(
                    "Choose backend, direction, and data type, then load a preview."
                )
            elif rec.state == "preview":
                rec.step_hint = _(
                    "Edit rows if needed, select what to transfer, then review."
                )
            elif rec.state == "confirm":
                rec.step_hint = _(
                    "Confirm %(count)s selected row(s), then transfer now."
                ) % {"count": rec.selected_count}
            elif rec.state == "done":
                rec.step_hint = _("Transfer finished. Open Jobs or Logs for detail.")
            else:
                rec.step_hint = False

    @api.depends("data_type", "direction")
    def _compute_flags(self):
        for rec in self:
            rec.is_partner_type = rec.data_type in ("customers", "suppliers")
            rec.is_product_type = rec.data_type == "products"
            rec.is_invoice_type = rec.data_type == "invoices"
            rec.is_import = rec.direction == "import"

    @api.depends("line_ids", "line_ids.selected", "line_ids.match_status")
    def _compute_counts(self):
        for rec in self:
            lines = rec.line_ids
            selected = lines.filtered("selected")
            rec.line_count = len(lines)
            rec.selected_count = len(selected)
            rec.new_count = len(selected.filtered(lambda l: l.match_status == "new"))
            rec.update_count = len(selected.filtered(lambda l: l.match_status == "update"))
            rec.skip_count = len(lines) - len(selected)
            rec.selected_line_ids = selected

    def action_open_backend(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sage Backends"),
            "res_model": "sage.backend",
            "view_mode": "tree,form",
            "target": "current",
        }

    def action_select_all(self):
        self.line_ids.filtered(lambda l: not l.skip_reason).write({"selected": True})
        return self._reload()

    def action_deselect_all(self):
        self.line_ids.write({"selected": False})
        return self._reload()

    def action_back_setup(self):
        self.write({"state": "setup"})
        return self._reload()

    def action_back_preview(self):
        self.write({"state": "preview"})
        return self._reload()

    def action_goto_confirm(self):
        self.ensure_one()
        selected = self.line_ids.filtered(lambda l: l.selected and not l.skip_reason)
        if not selected:
            raise UserError(_("Select at least one row to transfer."))
        self.write({"state": "confirm"})
        return self._reload()

    def _reload(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sage.transfer.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_load_preview(self):
        self.ensure_one()
        if not self.backend_id:
            raise UserError(_("Select a Sage backend first."))
        self.line_ids.unlink()
        if self.direction == "import":
            truncated = self._load_import_preview()
        else:
            truncated = self._load_export_preview()
        note = _("%s row(s) loaded.") % len(self.line_ids)
        if truncated:
            note += _(" Showing the first %s. Narrow the search to see others.") % PREVIEW_LIMIT
        self.write({
            "state": "preview",
            "truncated": truncated,
            "preview_note": note,
        })
        return self._reload()

    def _load_import_preview(self):
        path = KIND_PATH[self.data_type]
        extra = {}
        if self.search:
            extra["q"] = self.search
        items = []
        cursor = None
        truncated = False
        while len(items) < PREVIEW_LIMIT:
            page, next_cursor, has_more = self.env["sage.client"].get_page(
                self.backend_id,
                path,
                cursor=cursor,
                limit=min(200, PREVIEW_LIMIT - len(items)),
                extra=extra or None,
            )
            items.extend(page or [])
            if not has_more:
                break
            if len(items) >= PREVIEW_LIMIT:
                truncated = True
                break
            cursor = next_cursor
            if not cursor:
                truncated = bool(has_more)
                break
        for row in items[:PREVIEW_LIMIT]:
            self._create_import_line(row)
        return truncated

    def _match_partner(self, code):
        if not code:
            return self.env["res.partner"]
        Partner = self.env["res.partner"].sudo()
        rec = Partner.search([("x_pastel_code", "=", code)], limit=1)
        if rec:
            return rec
        return Partner.search([("sage_code", "=", code)], limit=1)

    def _match_product(self, code):
        if not code:
            return self.env["product.template"]
        Product = self.env["product.template"].sudo()
        rec = Product.search([("x_pastel_item_code", "=", code)], limit=1)
        if rec:
            return rec
        return Product.search([("sage_code", "=", code)], limit=1)

    def _create_import_line(self, row):
        kind = self.data_type
        vals = {
            "wizard_id": self.id,
            "selected": True,
            "payload_json": json.dumps(row, default=str),
        }
        if kind in ("customers", "suppliers"):
            code = (row.get("code") or "").strip()
            partner = self._match_partner(code)
            vals.update({
                "code": code,
                "name": row.get("name") or code,
                "phone": row.get("phone") or False,
                "email": row.get("email") or False,
                "tax_code": row.get("tax_code") or False,
                "credit_limit": row.get("credit_limit") or 0,
                "match_status": "update" if partner else "new",
                "odoo_res_model": "res.partner" if partner else False,
                "odoo_res_id": partner.id if partner else 0,
            })
        elif kind == "products":
            code = (row.get("code") or "").strip()
            product = self._match_product(code)
            vals.update({
                "code": code,
                "name": row.get("name") or code,
                "tax_code": row.get("tax_code") or False,
                "match_status": "update" if product else "new",
                "odoo_res_model": "product.template" if product else False,
                "odoo_res_id": product.id if product else 0,
            })
        else:
            doc_no = (row.get("doc_no") or "").strip()
            existing = self.env["account.move"].sudo().search(
                [("x_pastel_doc_no", "=", doc_no)], limit=1
            )
            exists = bool(existing)
            vals.update({
                "code": doc_no,
                "doc_no": doc_no,
                "name": row.get("customer_code") or doc_no,
                "customer_code": row.get("customer_code") or False,
                "invoice_date": row.get("invoice_date") and str(row.get("invoice_date"))[:10] or False,
                "amount": row.get("amount_total") or 0,
                "match_status": "exists" if exists else "new",
                "selected": not exists,
                "skip_reason": _("Already in Odoo") if exists else False,
                "odoo_res_model": "account.move" if existing else False,
                "odoo_res_id": existing.id if existing else 0,
            })
        line = self.env["sage.transfer.line"].create(vals)
        if kind == "invoices":
            for ln in row.get("lines") or []:
                self.env["sage.transfer.invoice.line"].create({
                    "transfer_line_id": line.id,
                    "product_code": ln.get("product_code") or False,
                    "name": ln.get("name") or False,
                    "quantity": ln.get("quantity") or 1.0,
                    "price_unit": ln.get("price_unit") or 0.0,
                    "tax_code": ln.get("tax_code") or False,
                })
        return line

    def _load_export_preview(self):
        company = self.backend_id.company_id
        truncated = False
        kind = self.data_type
        if kind in ("customers", "suppliers"):
            domain = [("company_id", "in", [company.id, False])]
            if kind == "customers":
                domain.append(("customer_rank", ">", 0))
            else:
                domain.append(("supplier_rank", ">", 0))
            if self.search:
                domain += ["|", ("name", "ilike", self.search), ("sage_code", "ilike", self.search)]
            partners = self.env["res.partner"].search(domain, limit=PREVIEW_LIMIT + 1)
            if len(partners) > PREVIEW_LIMIT:
                truncated = True
                partners = partners[:PREVIEW_LIMIT]
            for partner in partners:
                code = (partner.x_pastel_code or partner.sage_code or partner.ref or "").strip()
                skip = False
                reason = False
                if not code:
                    skip = True
                    reason = _("No Sage code")
                if kind == "suppliers":
                    skip = True
                    reason = _("Supplier upsert is not supported by this Sage adapter")
                payload = {
                    "code": code,
                    "name": partner.name,
                    "phone": partner.phone,
                    "email": partner.email,
                    "tax_code": partner.x_pastel_tax_code,
                    "credit_limit": partner.x_pastel_credit_limit,
                    "currency_code": partner.x_pastel_currency_code,
                    "odoo_res_model": "res.partner",
                    "odoo_res_id": partner.id,
                }
                self.env["sage.transfer.line"].create({
                    "wizard_id": self.id,
                    "selected": not skip,
                    "code": code or partner.display_name,
                    "name": partner.name,
                    "phone": partner.phone,
                    "email": partner.email,
                    "tax_code": partner.x_pastel_tax_code,
                    "credit_limit": partner.x_pastel_credit_limit or 0,
                    "match_status": "skip" if skip else "update",
                    "skip_reason": reason,
                    "odoo_res_model": "res.partner",
                    "odoo_res_id": partner.id,
                    "payload_json": json.dumps(payload, default=str),
                })
        elif kind == "products":
            domain = [("company_id", "in", [company.id, False])]
            if self.search:
                domain += ["|", "|", ("name", "ilike", self.search),
                           ("default_code", "ilike", self.search),
                           ("sage_code", "ilike", self.search)]
            products = self.env["product.template"].search(domain, limit=PREVIEW_LIMIT + 1)
            if len(products) > PREVIEW_LIMIT:
                truncated = True
                products = products[:PREVIEW_LIMIT]
            for product in products:
                code = (product.x_pastel_item_code or product.sage_code or product.default_code or "").strip()
                skip = not bool(code)
                payload = {
                    "code": code,
                    "name": product.name,
                    "tax_code": product.x_pastel_tax_code,
                    "odoo_res_model": "product.template",
                    "odoo_res_id": product.id,
                }
                self.env["sage.transfer.line"].create({
                    "wizard_id": self.id,
                    "selected": not skip,
                    "code": code or product.display_name,
                    "name": product.name,
                    "tax_code": product.x_pastel_tax_code,
                    "match_status": "skip" if skip else "update",
                    "skip_reason": _("No Sage item code") if skip else False,
                    "odoo_res_model": "product.template",
                    "odoo_res_id": product.id,
                    "payload_json": json.dumps(payload, default=str),
                })
        else:
            domain = [
                ("company_id", "=", company.id),
                ("state", "=", "posted"),
                ("move_type", "in", ("out_invoice", "out_refund")),
            ]
            if self.date_from:
                domain.append(("invoice_date", ">=", self.date_from))
            if self.search:
                domain += ["|", ("name", "ilike", self.search), ("partner_id.name", "ilike", self.search)]
            moves = self.env["account.move"].search(domain, limit=PREVIEW_LIMIT + 1)
            if len(moves) > PREVIEW_LIMIT:
                truncated = True
                moves = moves[:PREVIEW_LIMIT]
            sync = self.env["sage.sync"]
            for move in moves:
                try:
                    payload = sync._build_invoice_payload(move, self.backend_id)
                    skip = False
                    reason = False
                except UserError as exc:
                    payload = {
                        "doc_no": move.sage_doc_no or move.name,
                        "customer_code": "",
                        "invoice_date": move.invoice_date and move.invoice_date.isoformat(),
                        "amount_total": move.amount_total,
                        "lines": [],
                    }
                    skip = True
                    reason = str(exc)
                payload["odoo_res_model"] = "account.move"
                payload["odoo_res_id"] = move.id
                line = self.env["sage.transfer.line"].create({
                    "wizard_id": self.id,
                    "selected": not skip,
                    "code": payload.get("doc_no") or move.name,
                    "doc_no": payload.get("doc_no") or move.name,
                    "name": move.partner_id.display_name,
                    "customer_code": payload.get("customer_code"),
                    "invoice_date": move.invoice_date,
                    "amount": move.amount_total,
                    "match_status": "skip" if skip else "update",
                    "skip_reason": reason,
                    "odoo_res_model": "account.move",
                    "odoo_res_id": move.id,
                    "payload_json": json.dumps(payload, default=str),
                })
                for ln in payload.get("lines") or []:
                    self.env["sage.transfer.invoice.line"].create({
                        "transfer_line_id": line.id,
                        "product_code": ln.get("product_code") or False,
                        "name": ln.get("name") or False,
                        "quantity": ln.get("quantity") or 1.0,
                        "price_unit": ln.get("price_unit") or 0.0,
                        "tax_code": ln.get("tax_code") or False,
                    })
        return truncated

    def action_transfer(self):
        self.ensure_one()
        selected = self.line_ids.filtered(lambda l: l.selected and not l.skip_reason)
        if not selected:
            raise UserError(_("Select at least one row to transfer."))
        rows = [line.to_payload() for line in selected]
        job_type = "transfer_import" if self.direction == "import" else "transfer_export"
        payload = {"kind": self.data_type, "rows": rows, "direction": self.direction}
        Job = self.env["sage.job"].sudo()
        job = Job.enqueue(
            self.backend_id,
            job_type,
            payload=payload,
        )
        job.action_process_now()
        self.write({
            "state": "done",
            "result_text": self.env["sage.job"]._pretty_json(job.result) or _("Done"),
        })
        return self._reload()

    def action_open_jobs(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Sage Jobs"),
            "res_model": "sage.job",
            "view_mode": "tree,form",
            "domain": [("backend_id", "=", self.backend_id.id)],
        }

    def action_open_logs(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Sage Logs"),
            "res_model": "sage.sync.log",
            "view_mode": "tree,form",
            "domain": [("backend_id", "=", self.backend_id.id)],
        }


class SageTransferLine(models.TransientModel):
    """One preview row the user can select and edit."""

    _name = "sage.transfer.line"
    _description = "Sage Transfer Preview Line"

    wizard_id = fields.Many2one("sage.transfer.wizard", required=True, ondelete="cascade")
    selected = fields.Boolean(default=True)
    code = fields.Char(string="Sage code", required=True)
    name = fields.Char()
    phone = fields.Char()
    email = fields.Char()
    tax_code = fields.Char()
    credit_limit = fields.Float()
    doc_no = fields.Char()
    customer_code = fields.Char()
    invoice_date = fields.Date()
    amount = fields.Float()
    match_status = fields.Selection(
        [
            ("new", "New"),
            ("update", "Update"),
            ("exists", "Already exists"),
            ("skip", "Cannot transfer"),
        ],
        default="new",
    )
    skip_reason = fields.Char()
    odoo_res_model = fields.Char()
    odoo_res_id = fields.Integer()
    payload_json = fields.Text()
    invoice_line_ids = fields.One2many("sage.transfer.invoice.line", "transfer_line_id")

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in (
            "name", "phone", "email", "tax_code", "credit_limit",
            "code", "doc_no", "customer_code", "invoice_date", "amount", "selected",
        )):
            for rec in self:
                rec._sync_payload()
        return res

    def _sync_payload(self):
        self.ensure_one()
        try:
            data = json.loads(self.payload_json or "{}")
        except Exception:
            data = {}
        data["code"] = self.code
        data["name"] = self.name
        if self.phone is not False:
            data["phone"] = self.phone
        if self.email is not False:
            data["email"] = self.email
        if self.tax_code is not False:
            data["tax_code"] = self.tax_code
        data["credit_limit"] = self.credit_limit
        if self.doc_no:
            data["doc_no"] = self.doc_no
        if self.customer_code:
            data["customer_code"] = self.customer_code
        if self.invoice_date:
            data["invoice_date"] = self.invoice_date.isoformat()
        data["amount_total"] = self.amount
        if self.invoice_line_ids:
            data["lines"] = [ln.to_dict() for ln in self.invoice_line_ids]
        if self.odoo_res_id:
            data["odoo_res_id"] = self.odoo_res_id
            data["odoo_res_model"] = self.odoo_res_model
        super(SageTransferLine, self).write({"payload_json": json.dumps(data, default=str)})

    def to_payload(self):
        self.ensure_one()
        self._sync_payload()
        try:
            return json.loads(self.payload_json or "{}")
        except Exception:
            return {"code": self.code, "name": self.name}


class SageTransferInvoiceLine(models.TransientModel):
    """Editable invoice line on a preview row."""

    _name = "sage.transfer.invoice.line"
    _description = "Sage Transfer Invoice Line"

    transfer_line_id = fields.Many2one("sage.transfer.line", required=True, ondelete="cascade")
    product_code = fields.Char()
    name = fields.Char()
    quantity = fields.Float(default=1.0)
    price_unit = fields.Float()
    tax_code = fields.Char()

    def write(self, vals):
        res = super().write(vals)
        self.mapped("transfer_line_id")._sync_payload()
        return res

    def to_dict(self):
        self.ensure_one()
        return {
            "product_code": self.product_code,
            "name": self.name,
            "quantity": self.quantity,
            "price_unit": self.price_unit,
            "tax_code": self.tax_code,
        }
