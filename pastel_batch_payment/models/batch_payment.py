from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import requests
import logging
import json
_logger = logging.getLogger(__name__)
# -------------------------------------------------------------------
# Settings (unchanged)
# -------------------------------------------------------------------
class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pastel_bridge_base = fields.Char(string="Pastel Bridge Base URL")
    pastel_bridge_key = fields.Char(string="Pastel Bridge API Key")

    def set_values(self):
        res = super().set_values()
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("pastel_batch_payment.bridge_base", self.pastel_bridge_base or "")
        params.set_param("pastel_batch_payment.bridge_key", self.pastel_bridge_key or "")
        return res

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env["ir.config_parameter"].sudo()
        res.update(
            pastel_bridge_base=params.get_param("pastel_batch_payment.bridge_base", ""),
            pastel_bridge_key=params.get_param("pastel_batch_payment.bridge_key", ""),
        )
        return res


# -------------------------------------------------------------------
# Batch Payment
# -------------------------------------------------------------------
class BatchPayment(models.Model):
    _name = "batch.payment"
    _description = "Batch Payment"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    # Header
    name = fields.Char(default="/", readonly=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("validated", "Validated"),
        ("exported", "Exported"),
    ], default="draft", tracking=True)

    payment_date = fields.Date(required=True, default=fields.Date.context_today)

    partner_type = fields.Selection(
        [("customer", "Customer"), ("supplier", "Supplier")],
        required=True, default="customer"
    )

    # NEW: Header-level customer selector (requested)
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        domain="[('customer_rank','>',0)]",
        help="Filter posted payments by this customer."
    )

    journal_id = fields.Many2one("account.journal", required=True, domain="[('type','in',['bank','cash'])]")

    # NEW: Payment method line (journal-bound)
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Payment Method",
        domain="[('journal_id','=',journal_id)]",
        help="Filters posted payments by this method."
    )

    currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id)
    company_id  = fields.Many2one("res.company", default=lambda s: s.env.company, required=True)

    line_ids = fields.One2many("batch.payment.line", "batch_id", string="Lines")

    amount_total = fields.Monetary(currency_field="currency_id", compute="_compute_amounts", store=True)
    exported_ref = fields.Char("Export Reference", readonly=True)
    note = fields.Text()

    @api.depends("line_ids.amount")
    def _compute_amounts(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped("amount"))

    # ----------------------------------------------------------------
    # EXISTING: Load open items (kept as-is for your previous flow)
    # ----------------------------------------------------------------
    def action_load_open_items(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only draft batches can load lines"))

        dom = [("move_id.state", "=", "posted"),
               ("reconciled", "=", False),
               ("company_id", "=", self.company_id.id)]
        if self.partner_type == "customer":
            dom += [("account_id.account_type", "=", "asset_receivable")]
        else:
            dom += [("account_id.account_type", "=", "liability_payable")]

        items = self.env["account.move.line"].search(dom, order="date asc", limit=500)
        if not items:
            raise UserError(_("No open items found."))

        new_lines = []
        for aml in items:
            residual = aml.amount_residual if aml.currency_id != aml.company_currency_id else aml.amount_residual
            amount = abs(residual)
            if amount <= 0:
                continue
            new_lines.append((0, 0, {
                "move_id": aml.move_id.id,
                "move_line_id": aml.id,
                "communication": aml.move_id.name or aml.ref or "",
                "amount": amount,
            }))
        if new_lines:
            self.write({"line_ids": new_lines})

    # ----------------------------------------------------------------
    # NEW: Load posted account.payment filtered by Customer/Journal/Method
    # ----------------------------------------------------------------
    def action_load_posted_payments(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only draft batches can load payments"))

        domain = [
            ("state", "=", "posted"),
            ("company_id", "=", self.company_id.id),
            ("journal_id", "=", self.journal_id.id),
        ]
        # Infer inbound/outbound by partner_type for clarity
        # (Not strictly required to search, but documents intent)
        if self.partner_type == "customer":
            domain.append(("partner_type", "=", "customer"))
            if self.partner_id:
                domain.append(("partner_id", "=", self.partner_id.id))
        else:
            domain.append(("partner_type", "=", "supplier"))
            if self.partner_id:
                domain.append(("partner_id", "=", self.partner_id.id))

        if self.payment_method_line_id:
            domain.append(("payment_method_line_id", "=", self.payment_method_line_id.id))

        payments = self.env["account.payment"].search(domain, order="date asc", limit=500)
        if not payments:
            raise UserError(_("No posted payments found for the selected filters."))

        # Avoid duplicates in the batch
        existing_payment_ids = set(self.line_ids.mapped("payment_id").ids)
        to_add = []
        for p in payments:
            if p.id in existing_payment_ids:
                continue
            to_add.append((0, 0, {
                "payment_id": p.id,
                "communication": p.ref or p.name or "",
                "amount": abs(p.amount),
            }))

        if not to_add:
            raise UserError(_("All matching posted payments are already in this batch."))

        self.write({"line_ids": to_add})

    # ----------------------------------------------------------------
    # VALIDATE: now just ensures lines are valid (no creation needed)
    # For the “posted payment” flow, we don’t create new account.payment
    # ----------------------------------------------------------------
    def action_validate(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft batches can be validated."))
            if not rec.line_ids:
                raise UserError(_("No lines."))

            # If a line is linked to a posted payment, accept it.
            # If not linked, it came from the "open items" loader; create & post a payment for it.
            for ln in rec.line_ids:
                if ln.payment_id:
                    if ln.payment_id.state != "posted":
                        raise UserError(_("Payment %s is not posted.") % (ln.payment_id.display_name,))
                    continue

                # Fallback: create payments for open-item lines (your old flow)
                pay_vals = {
                    "date": rec.payment_date,
                    "journal_id": rec.journal_id.id,
                    "currency_id": rec.currency_id.id or rec.company_id.currency_id.id,
                    "amount": ln.amount,
                    "ref": ln.communication or rec.name or "",
                    "partner_id": ln.partner_id.id if ln.partner_id else False,
                    "payment_type": "inbound" if rec.partner_type == "customer" else "outbound",
                    "partner_type": "customer" if rec.partner_type == "customer" else "supplier",
                    "payment_method_line_id": rec.payment_method_line_id.id if rec.payment_method_line_id else False,
                }
                payment = self.env["account.payment"].create(pay_vals)
                payment.action_post()

                if ln.move_line_id and not ln.move_line_id.reconciled:
                    lines_to_reconcile = ln.move_line_id + payment.move_id.line_ids.filtered(
                        lambda l: l.account_id == ln.move_line_id.account_id and not l.reconciled
                    )
                    lines_to_reconcile.reconcile()

                ln.payment_id = payment.id

            if rec.name == "/":
                rec.name = rec.env["ir.sequence"].next_by_code("batch.payment") or f"BATCH/{rec.id}"
            rec.state = "validated"

    # ----------------------------------------------------------------
    # EXPORT (unchanged except: prefer payment fields when available)
    # ----------------------------------------------------------------
    def action_export_sage(self):
        for rec in self:
            if rec.state != "validated":
                raise UserError(_("Only validated batches can be exported."))

            base = self.env["ir.config_parameter"].sudo().get_param("pastel_batch_payment.bridge_base")
            key = self.env["ir.config_parameter"].sudo().get_param("pastel_batch_payment.bridge_key")
            if not base or not key:
                raise UserError(_("Bridge base URL or API key not configured."))

            lines = []
            for ln in rec.line_ids:
                partner = ln.partner_id
                partner_code = (getattr(partner, "x_pastel_code", "") or "").strip() or \
                               (partner.ref or partner.name or "").strip()

                # Try to carry a doc number if linked to a move (optional)
                doc_no = ""
                if ln.move_id:
                     doc_no = ln.move_id.x_pastel_doc_no or ln.move_id.payment_reference or ln.move_id.name or ""
                    # partner_code = (ln.partner_id.x_pastel_code or "").strip() or (
                    #             ln.partner_id.ref or ln.partner_id.name or "").strip()
                    # doc_no = str(rec.id)
                lines.append({
                    "partner_code": partner_code,
                    "invoice_doc_no": doc_no or None,
                    "amount": float(ln.amount),
                    "reference": ln.communication or rec.name or "",
                    "currency_code": (rec.currency_id.name or "ZAR"),
                })

            payload = {
                "batch_ref": rec.name,
                "payment_date": str(rec.payment_date),
                "partner_type": rec.partner_type,
                "journal_code": rec.journal_id.code,
                "currency_code": rec.currency_id.name or "ZAR",
                "lines": lines,
            }


            # Server log (exactly what we’re exporting)
            _logger.info("Exporting BatchPayment %s to Sage with payload:\n%s", rec.name,
                         json.dumps(payload, indent=2, ensure_ascii=False))
            url = base.rstrip("/") + "/payments/batch"
            headers = {"x-api-key": key}
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=60)
                r.raise_for_status()
                data = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
            except Exception as e:
                raise UserError(_("Sage export failed: %s") % e)

            rec.exported_ref = data.get("batch_id") or data.get("reference") or rec.name
            rec.state = "exported"

    @api.onchange("journal_id", "payment_method_line_id", "partner_id", "company_id")
    def _onchange_filters_prune_lines(self):
        for rec in self:
            if not rec.line_ids:
                continue
            to_keep = rec.line_ids.filtered(lambda ln:
                                            ln.payment_id
                                            and ln.payment_id.state == "posted"
                                            and (not rec.journal_id or ln.payment_id.journal_id == rec.journal_id)
                                            and (not rec.company_id or ln.payment_id.company_id == rec.company_id)
                                            and (
                                                        not rec.payment_method_line_id or ln.payment_id.payment_method_line_id == rec.payment_method_line_id)
                                            and (
                                                        rec.partner_type != "customer" or not rec.partner_id or ln.payment_id.partner_id == rec.partner_id)
                                            )
            if len(to_keep) != len(rec.line_ids):
                rec.line_ids = [(6, 0, to_keep.ids)]

# -------------------------------------------------------------------
# Lines: now centered on account.payment with related columns
# -------------------------------------------------------------------

class BatchPaymentLine(models.Model):
    _name = "batch.payment.line"
    _description = "Batch Payment Line"
    _order = "id asc"

    batch_id = fields.Many2one("batch.payment", required=True, ondelete="cascade")
    payment_id = fields.Many2one("account.payment", string="Payment")

    # Display columns (related)
    number = fields.Char(related="payment_id.name", store=True)
    date = fields.Date(related="payment_id.date", store=True)
    journal_id = fields.Many2one("account.journal", related="payment_id.journal_id", store=True)
    company_id = fields.Many2one("res.company", related="payment_id.company_id", store=True)
    payment_method_line_id = fields.Many2one("account.payment.method.line", related="payment_id.payment_method_line_id", store=True)
    partner_id = fields.Many2one("res.partner", related="payment_id.partner_id", store=True, string="Customer/Supplier")
    status = fields.Selection(related="payment_id.state", store=True, string="Status")

    amount = fields.Monetary(currency_field="currency_id",
                             compute="_compute_amount_from_payment", store=True)
    currency_id = fields.Many2one(related="batch_id.currency_id", store=True)

    # legacy fields (kept)
    move_id = fields.Many2one("account.move", string="Invoice/Bill")
    move_line_id = fields.Many2one("account.move.line", string="Open Item")
    communication = fields.Char()
    # selected = fields.Boolean(string="Select")

    @api.depends("payment_id.amount", "payment_id.currency_id")
    def _compute_amount_from_payment(self):
        for ln in self:
            ln.amount = abs(ln.payment_id.amount) if ln.payment_id else (ln.amount or 0.0)

    # ... your model definitions ...

    def _check_payment_matches_header(self):
        """
        Called on create/write of batch.payment.line to enforce that chosen payment
        matches the batch header filters (journal, company, method, state).
        Make sure EVERY formatted string uses % with a dict (mapping).
        """
        for line in self:
            pay = line.payment_id
            batch = line.batch_id
            if not pay or not batch:
                continue

            # journal must match
            if batch.journal_id and pay.journal_id != batch.journal_id:
                msg = _("Payment %(p)s journal (%(pj)s) doesn't match batch journal (%(bj)s).") % {
                    "p": pay.display_name,
                    "pj": pay.journal_id.display_name or pay.journal_id.name,
                    "bj": batch.journal_id.display_name or batch.journal_id.name,
                }
                raise ValidationError(msg)

            # company must match
            if batch.company_id and pay.company_id != batch.company_id:
                msg = _("Payment %(p)s company (%(pc)s) doesn't match batch company (%(bc)s).") % {
                    "p": pay.display_name,
                    "pc": pay.company_id.display_name or pay.company_id.name,
                    "bc": batch.company_id.display_name or batch.company_id.name,
                }
                raise ValidationError(msg)

            # posted only
            if pay.state != "posted":
                msg = _("Payment %(p)s is not posted (state: %(st)s).") % {
                    "p": pay.display_name,
                    "st": pay.state,
                }
                raise ValidationError(msg)

            # optional: payment method line must match when batch has one fixed (if you store it)
            if hasattr(batch, "payment_method_line_id") and batch.payment_method_line_id:
                if pay.payment_method_line_id != batch.payment_method_line_id:
                    msg = _("Payment %(p)s method (%(pm)s) doesn't match batch method (%(bm)s).") % {
                        "p": pay.display_name,
                        "pm": pay.payment_method_line_id.display_name or pay.payment_method_line_id.name,
                        "bm": batch.payment_method_line_id.display_name or batch.payment_method_line_id.name,
                    }
                    raise ValidationError(msg)




    # @api.constrains("payment_id", "batch_id")
    # def _check_payment_matches_header(self):
    #     for ln in self:
    #         if not ln.payment_id:
    #             continue
    #         pay = ln.payment_id
    #         hdr = ln.batch_id
    #
    #         # must be posted
    #         if pay.state != "posted":
    #             raise ValidationError(_("Only posted payments can be added to the batch."))
    #
    #         # journal must match
    #         if hdr.journal_id and pay.journal_id != hdr.journal_id:
    #             raise ValidationError(_("Payment %(p)s journal doesn't match batch journal.",
    #                                     {"p": pay.display_name}))
    #
    #         # company must match
    #         if hdr.company_id and pay.company_id != hdr.company_id:
    #             raise ValidationError(_("Payment %(p)s company doesn't match batch company.",
    #                                     {"p": pay.display_name}))
    #
    #         # payment method must match if set on header
    #         if hdr.payment_method_line_id and pay.payment_method_line_id != hdr.payment_method_line_id:
    #             raise ValidationError(_("Payment %(p)s method doesn't match batch payment method.",
    #                                     {"p": pay.display_name}))
    #
    #         # partner/customer filter if header customer provided (for customer batches)
    #         if hdr.partner_type == "customer" and hdr.partner_id and pay.partner_id != hdr.partner_id:
    #             raise ValidationError(_("Payment %(p)s customer doesn't match the batch customer.",
    #                                     {"p": pay.display_name}))

# class BatchPaymentLine(models.Model):
#     _name = "batch.payment.line"
#     _description = "Batch Payment Line"
#     _order = "id asc"
#
#     batch_id = fields.Many2one("batch.payment", required=True, ondelete="cascade")
#
#     # The chosen posted payment (if you load via 'Load Posted Payments')
#     payment_id = fields.Many2one("account.payment", string="Payment")
#
#     # Show required fields (all related to payment_id)
#     number = fields.Char(string="Number", related="payment_id.name", store=True)
#     date = fields.Date(related="payment_id.date", store=True)
#     journal_id = fields.Many2one("account.journal", related="payment_id.journal_id", store=True)
#     company_id = fields.Many2one("res.company", related="payment_id.company_id", store=True)
#     payment_method_line_id = fields.Many2one("account.payment.method.line", related="payment_id.payment_method_line_id", store=True)
#     partner_id = fields.Many2one("res.partner", related="payment_id.partner_id", store=True, string="Customer/Supplier")
#     status = fields.Selection(related="payment_id.state", store=True, string="Status")
#
#     # Amount shown on the line (comes from the payment when selected)
#     amount = fields.Monetary(currency_field="currency_id",
#                              compute="_compute_amount_from_payment",
#                              store=True)
#     currency_id = fields.Many2one(related="batch_id.currency_id", store=True)
#
#     # Optional legacy fields from the “open items” flow (kept for compatibility)
#     move_id = fields.Many2one("account.move", string="Invoice/Bill")
#     move_line_id = fields.Many2one("account.move.line", string="Open Item")
#     communication = fields.Char()
#
#     @api.depends("payment_id.amount", "payment_id.currency_id")
#     def _compute_amount_from_payment(self):
#         for ln in self:
#             ln.amount = abs(ln.payment_id.amount) if ln.payment_id else (ln.amount or 0.0)
#

# # pastel_batch_payment/models/batch_payment.py
# from odoo import api, fields, models, _
# from odoo.exceptions import UserError
# import requests
#
# class ResConfigSettings(models.TransientModel):
#     _inherit = "res.config.settings"
#
#     # Single source of truth (stored automatically in ir.config_parameter)
#     pastel_bridge_base = fields.Char(
#         string="Pastel Bridge Base URL",
#         config_parameter="pastel.bridge.base",
#         help="e.g. http://127.0.0.1:8787",
#     )
#     pastel_bridge_key = fields.Char(
#         string="Pastel Bridge API Key",
#         config_parameter="pastel.bridge.key",
#     )
#
#
# class BatchPayment(models.Model):
#     _name = "batch.payment"
#     _description = "Batch Payment"
#     _order = "id desc"
#
#     name = fields.Char(default="/", readonly=True, copy=False)
#     state = fields.Selection(
#         [("draft", "Draft"), ("validated", "Validated"), ("exported", "Exported")],
#         default="draft", tracking=True
#     )
#
#     payment_date = fields.Date(required=True, default=fields.Date.context_today)
#     partner_type = fields.Selection(
#         [("customer", "Customer"), ("supplier", "Supplier")],
#         required=True, default="customer"
#     )
#     journal_id = fields.Many2one(
#         "account.journal", required=True,
#         domain="[('type','in',['bank','cash'])]"
#     )
#     currency_id = fields.Many2one(
#         "res.currency", default=lambda s: s.env.company.currency_id
#     )
#     line_ids = fields.One2many("batch.payment.line", "batch_id", string="Lines")
#     amount_total = fields.Monetary(currency_field="currency_id",
#                                    compute="_compute_amounts", store=True)
#     company_id = fields.Many2one("res.company",
#                                  default=lambda s: s.env.company, required=True)
#     exported_ref = fields.Char("Export Reference", readonly=True, copy=False)
#     note = fields.Text()
#
#     @api.depends("line_ids.amount")
#     def _compute_amounts(self):
#         for rec in self:
#             rec.amount_total = sum(rec.line_ids.mapped("amount"))
#
#     def action_load_open_items(self):
#         self.ensure_one()
#         if self.state != "draft":
#             raise UserError(_("Only draft batches can load lines"))
#
#         dom = [
#             ("move_id.state", "=", "posted"),
#             ("reconciled", "=", False),
#             ("company_id", "=", self.company_id.id),
#         ]
#         if self.partner_type == "customer":
#             dom += [("account_id.account_type", "=", "asset_receivable")]
#         else:
#             dom += [("account_id.account_type", "=", "liability_payable")]
#
#         items = self.env["account.move.line"].search(dom, order="date asc", limit=500)
#         if not items:
#             raise UserError(_("No open items found."))
#
#         new_lines = []
#         for aml in items:
#             # use amount_residual_currency if multi-currency, else residual in company currency
#             amount = abs(aml.amount_residual_currency or aml.amount_residual)
#             if amount <= 0:
#                 continue
#             new_lines.append((0, 0, {
#                 "partner_id": aml.partner_id.id,
#                 "move_id": aml.move_id.id,
#                 "move_line_id": aml.id,
#                 "communication": aml.move_id.name or aml.ref or "",
#                 "amount": amount,
#             }))
#         if new_lines:
#             self.write({"line_ids": new_lines})
#
#     def action_validate(self):
#         for rec in self:
#             if rec.state != "draft":
#                 raise UserError(_("Only draft batches can be validated."))
#             if not rec.line_ids:
#                 raise UserError(_("No lines."))
#
#             # Assign sequence now so export uses a stable batch_ref
#             if rec.name == "/":
#                 rec.name = rec.env["ir.sequence"].next_by_code("batch.payment") or f"BATCH/{rec.id}"
#
#             for ln in rec.line_ids:
#                 if ln.payment_id:
#                     continue
#                 pay_vals = {
#                     "date": rec.payment_date,
#                     "journal_id": rec.journal_id.id,
#                     "currency_id": rec.currency_id.id or rec.company_id.currency_id.id,
#                     "amount": ln.amount,
#                     "ref": ln.communication or rec.name or "",
#                     "partner_id": ln.partner_id.id,
#                     "payment_type": "inbound" if rec.partner_type == "customer" else "outbound",
#                     "partner_type": "customer" if rec.partner_type == "customer" else "supplier",
#                 }
#                 payment = self.env["account.payment"].create(pay_vals)
#                 payment.action_post()
#
#                 if ln.move_line_id and not ln.move_line_id.reconciled:
#                     lines_to_reconcile = ln.move_line_id + payment.move_id.line_ids.filtered(
#                         lambda l: l.account_id == ln.move_line_id.account_id and not l.reconciled
#                     )
#                     lines_to_reconcile.reconcile()
#
#                 ln.payment_id = payment.id
#
#             rec.state = "validated"
#
#     def action_export_sage(self):
#         for rec in self:
#             if rec.state != "validated":
#                 raise UserError(_("Only validated batches can be exported."))
#
#             # Read the SAME keys you set in settings (config_parameter above)
#             base = self.env["ir.config_parameter"].sudo().get_param("pastel.bridge.base")
#             key  = self.env["ir.config_parameter"].sudo().get_param("pastel.bridge.key")
#             if not base or not key:
#                 raise UserError(_("Bridge base URL or API key not configured."))
#
#             lines = []
#             for ln in rec.line_ids:
#                 partner_code = (ln.partner_id.x_pastel_code or "").strip() \
#                                or (ln.partner_id.ref or ln.partner_id.name or "").strip()
#                 # Try to link allocation to a doc number if you have one
#                 doc_no = ""
#                 if ln.move_id:
#                     doc_no = (ln.move_id.x_pastel_doc_no
#                               or ln.move_id.payment_reference
#                               or ln.move_id.name
#                               or "") or ""
#                 lines.append({
#                     "partner_code": partner_code,
#                     "invoice_doc_no": doc_no,
#                     "amount": float(ln.amount),
#                     "reference": ln.communication or rec.name or "",
#                     "currency_code": (rec.currency_id.name or "ZAR"),
#                 })
#
#             payload = {
#                 "batch_ref": rec.name,                     # stable natural key
#                 "payment_date": str(rec.payment_date),     # your bridge expects payment_date
#                 "partner_type": rec.partner_type,          # 'customer' or 'supplier'
#                 "journal_code": rec.journal_id.code,
#                 "currency_code": rec.currency_id.name or "ZAR",
#                 "lines": lines,
#             }
#
#             url = base.rstrip("/") + "/payments/batch"
#             headers = {"x-api-key": key}
#             try:
#                 r = requests.post(url, json=payload, headers=headers, timeout=60)
#                 resp_text = r.text
#                 r.raise_for_status()
#                 data = r.json() if r.headers.get("content-type","").lower().startswith("application/json") else {}
#             except Exception as e:
#                 # expose bridge body to quickly identify table/column issues
#                 raise UserError(_("Sage export failed: %s\n\nBridge said:\n%s") % (e, resp_text))
#
#             rec.exported_ref = data.get("batch_id") or data.get("reference") or rec.name
#             rec.state = "exported"
#
#
# class BatchPaymentLine(models.Model):
#     _name = "batch.payment.line"
#     _description = "Batch Payment Line"
#     _order = "id asc"
#
#     batch_id = fields.Many2one("batch.payment", required=True, ondelete="cascade")
#     partner_id = fields.Many2one("res.partner", required=True)
#     move_id = fields.Many2one("account.move", string="Invoice/Bill")
#     move_line_id = fields.Many2one("account.move.line", string="Open Item")
#     communication = fields.Char()
#     amount = fields.Monetary(required=True, currency_field="currency_id")
#     currency_id = fields.Many2one(related="batch_id.currency_id", store=True)
#     payment_id = fields.Many2one("account.payment", readonly=True)


# from odoo import api, fields, models, _
# from odoo.exceptions import UserError
# import requests
#
# class ResConfigSettings(models.TransientModel):
#     _inherit = "res.config.settings"
#
#     pastel_bridge_base = fields.Char(string="Pastel Bridge Base URL")
#     pastel_bridge_key = fields.Char(string="Pastel Bridge API Key")
#
#
#
#     def set_values(self):
#         res = super().set_values()
#         params = self.env["ir.config_parameter"].sudo()
#         params.set_param("pastel_batch_payment.bridge_base", self.pastel_bridge_base or "")
#         params.set_param("pastel_batch_payment.bridge_key", self.pastel_bridge_key or "")
#         return res
#
#     @api.model
#     def get_values(self):
#         res = super().get_values()
#         params = self.env["ir.config_parameter"].sudo()
#         res.update(
#             pastel_bridge_base=params.get_param("pastel_batch_payment.bridge_base", ""),
#             pastel_bridge_key=params.get_param("pastel_batch_payment.bridge_key", ""),
#         )
#         return res
#
#
# class BatchPayment(models.Model):
#     _name = "batch.payment"
#     _description = "Batch Payment"
#     _order = "id desc"
#
#     name = fields.Char(default="/", readonly=True)
#     state = fields.Selection([
#         ("draft", "Draft"),
#         ("validated", "Validated"),
#         ("exported", "Exported"),
#     ], default="draft", tracking=True)
#
#     payment_date = fields.Date(required=True, default=fields.Date.context_today)
#     partner_type = fields.Selection([("customer", "Customer"), ("supplier", "Supplier")], required=True, default="customer")
#     journal_id = fields.Many2one("account.journal", required=True, domain="[('type','in',['bank','cash'])]")
#     currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id)
#     line_ids = fields.One2many("batch.payment.line", "batch_id", string="Lines")
#     amount_total = fields.Monetary(currency_field="currency_id", compute="_compute_amounts", store=True)
#     company_id = fields.Many2one("res.company", default=lambda s: s.env.company, required=True)
#     exported_ref = fields.Char("Export Reference", readonly=True)
#     note = fields.Text()
#
#     @api.depends("line_ids.amount")
#     def _compute_amounts(self):
#         for rec in self:
#             rec.amount_total = sum(rec.line_ids.mapped("amount"))
#
#     def action_load_open_items(self):
#         self.ensure_one()
#         if self.state != "draft":
#             raise UserError(_("Only draft batches can load lines"))
#
#         dom = [("move_id.state", "=", "posted"),
#                ("reconciled", "=", False),
#                ("company_id", "=", self.company_id.id)]
#         if self.partner_type == "customer":
#             dom += [("account_id.account_type", "=", "asset_receivable")]
#         else:
#             dom += [("account_id.account_type", "=", "liability_payable")]
#
#         items = self.env["account.move.line"].search(dom, order="date asc", limit=500)
#         if not items:
#             raise UserError(_("No open items found."))
#
#         new_lines = []
#         for aml in items:
#             residual = aml.amount_residual if aml.currency_id != aml.company_currency_id else aml.amount_residual
#             amount = abs(residual)
#             if amount <= 0:
#                 continue
#             new_lines.append((0, 0, {
#                 "partner_id": aml.partner_id.id,
#                 "move_id": aml.move_id.id,
#                 "move_line_id": aml.id,
#                 "communication": aml.move_id.name or aml.ref or "",
#                 "amount": amount,
#             }))
#         if new_lines:
#             self.write({"line_ids": new_lines})
#
#     def action_validate(self):
#         for rec in self:
#             if rec.state != "draft":
#                 raise UserError(_("Only draft batches can be validated."))
#             if not rec.line_ids:
#                 raise UserError(_("No lines."))
#
#             for ln in rec.line_ids:
#                 if ln.payment_id:
#                     continue
#                 pay_vals = {
#                     "date": rec.payment_date,
#                     "journal_id": rec.journal_id.id,
#                     "currency_id": rec.currency_id.id or rec.company_id.currency_id.id,
#                     "amount": ln.amount,
#                     "ref": ln.communication or rec.name or "",
#                     "partner_id": ln.partner_id.id,
#                     "payment_type": "inbound" if rec.partner_type == "customer" else "outbound",
#                     "partner_type": "customer" if rec.partner_type == "customer" else "supplier",
#                 }
#                 payment = self.env["account.payment"].create(pay_vals)
#                 payment.action_post()
#
#                 if ln.move_line_id and not ln.move_line_id.reconciled:
#                     lines_to_reconcile = ln.move_line_id + payment.move_id.line_ids.filtered(
#                         lambda l: l.account_id == ln.move_line_id.account_id and not l.reconciled
#                     )
#                     lines_to_reconcile.reconcile()
#
#                 ln.payment_id = payment.id
#
#             if self.name == "/":
#                 self.name = self.env["ir.sequence"].next_by_code("batch.payment") or f"BATCH/{self.id}"
#             self.state = "validated"
#
#     def action_export_sage(self):
#         for rec in self:
#             if rec.state != "validated":
#                 raise UserError(_("Only validated batches can be exported."))
#
#             base = self.env["ir.config_parameter"].sudo().get_param("pastel_batch_payment.bridge_base")
#             key = self.env["ir.config_parameter"].sudo().get_param("pastel_batch_payment.bridge_key")
#             if not base or not key:
#                 raise UserError(_("Bridge base URL or API key not configured."))
#
#             lines = []
#             for ln in rec.line_ids:
#                 partner_code = (ln.partner_id.x_pastel_code or "").strip() or (ln.partner_id.ref or ln.partner_id.name or "").strip()
#                 doc_no = (ln.move_id.x_pastel_doc_no or ln.move_id.payment_reference or ln.move_id.name or "") if ln.move_id else ""
#                 lines.append({
#                     "partner_code": partner_code,
#                     "invoice_doc_no": doc_no,
#                     "amount": float(ln.amount),
#                     "reference": ln.communication or rec.name or "",
#                     "currency_code": (rec.currency_id.name or "ZAR"),
#                 })
#
#             payload = {
#                 "batch_ref": rec.name,
#                 "payment_date": str(rec.payment_date),
#                 "partner_type": rec.partner_type,
#                 "journal_code": rec.journal_id.code,
#                 "currency_code": rec.currency_id.name or "ZAR",
#                 "lines": lines,
#             }
#
#             url = base.rstrip("/") + "/payments/batch"
#             headers = {"x-api-key": key}
#             try:
#                 r = requests.post(url, json=payload, headers=headers, timeout=60)
#                 r.raise_for_status()
#                 data = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
#             except Exception as e:
#                 raise UserError(_("Sage export failed: %s") % e)
#
#             rec.exported_ref = data.get("batch_id") or data.get("reference") or rec.name
#             rec.state = "exported"
#
#
# class BatchPaymentLine(models.Model):
#     _name = "batch.payment.line"
#     _description = "Batch Payment Line"
#     _order = "id asc"
#
#     batch_id = fields.Many2one("batch.payment", required=True, ondelete="cascade")
#     partner_id = fields.Many2one("res.partner", required=True)
#     move_id = fields.Many2one("account.move", string="Invoice/Bill")
#     move_line_id = fields.Many2one("account.move.line", string="Open Item")
#     communication = fields.Char()
#     amount = fields.Monetary(required=True, currency_field="currency_id")
#     currency_id = fields.Many2one(related="batch_id.currency_id", store=True)
#     payment_id = fields.Many2one("account.payment", readonly=True)
#
#
# class ResConfigSettings(models.TransientModel):
#     _inherit = 'res.config.settings'
#
#     pastel_bridge_base = fields.Char(string="Pastel Bridge Base URL", config_parameter='pastel.bridge.base')
#     pastel_bridge_key  = fields.Char(string="Pastel Bridge API Key", config_parameter='pastel.bridge.key')
#
