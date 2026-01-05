# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_is_zero
import requests
import logging
import json

_logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Settings
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
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default="/", readonly=True)

    state = fields.Selection([
        ("draft", "Draft"),
        ("validated", "Validated"),
        ("exported", "Exported"),
        ("paid", "Paid"),
    ], default="draft", tracking=True)

    payment_date = fields.Date(required=True, default=fields.Date.context_today)

    partner_type = fields.Selection(
        [("customer", "Customer"), ("supplier", "Supplier")],
        required=True,
        default="customer",
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        domain="[('customer_rank','>',0)]",
        help="Filter posted payments by this customer.",
    )

    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain="[('type','in',['bank','cash'])]",
    )

    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Payment Method",
        domain="[('journal_id','=',journal_id)]",
        help="Filters posted payments by this method.",
    )

    currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id)
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company, required=True)

    line_ids = fields.One2many("batch.payment.line", "batch_id", string="Lines")

    amount_total = fields.Monetary(currency_field="currency_id", compute="_compute_amounts", store=True)
    exported_ref = fields.Char("Export Reference", readonly=True)
    note = fields.Text()

    @api.depends("line_ids.amount")
    def _compute_amounts(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped("amount"))

    # ----------------------------------------------------------------
    # Load open items (unpaid AR/AP move lines)
    # ----------------------------------------------------------------
    def action_load_open_items(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only draft batches can load lines"))

        dom = [
            ("move_id.state", "=", "posted"),
            ("reconciled", "=", False),
            ("company_id", "=", self.company_id.id),
        ]
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
    # Load posted payments (and auto-link invoice using payment.batch_invoice_id)
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

        existing_payment_ids = set(self.line_ids.mapped("payment_id").ids)
        to_add = []
        for p in payments:
            if p.id in existing_payment_ids:
                continue

            move_id = p.batch_invoice_id.id if getattr(p, "batch_invoice_id", False) else False

            to_add.append((0, 0, {
                "payment_id": p.id,
                "communication": p.ref or p.name or "",
                "amount": abs(p.amount),
                "move_id": move_id,
            }))

        if not to_add:
            raise UserError(_("All matching posted payments are already in this batch."))

        self.write({"line_ids": to_add})

    # ----------------------------------------------------------------
    # Validate
    # ----------------------------------------------------------------
    def action_validate(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft batches can be validated."))
            if not rec.line_ids:
                raise UserError(_("No lines."))

            for ln in rec.line_ids:
                # A) already linked to a posted payment
                if ln.payment_id:
                    if ln.payment_id.state != "posted":
                        raise UserError(_("Payment %s is not posted.") % ln.payment_id.display_name)

                    if not ln.move_id and getattr(ln.payment_id, "batch_invoice_id", False):
                        ln.move_id = ln.payment_id.batch_invoice_id.id
                    continue

                # B) create payment using the official wizard (like UI)
                invoice = ln.move_id or (ln.move_line_id.move_id if ln.move_line_id else False)
                if not invoice:
                    raise UserError(_("Line has no invoice/open item to create a payment from."))

                if invoice.state != "posted":
                    raise UserError(_("Invoice %s must be posted before validating the batch.") % invoice.display_name)

                ctx = dict(self.env.context or {})
                ctx.update({
                    "active_model": "account.move",
                    "active_ids": [invoice.id],
                    "active_id": invoice.id,
                    # important: do NOT auto reconcile at register-payment time
                    "batch_skip_reconcile": True,
                })

                wizard_vals = {
                    "amount": ln.amount or invoice.amount_residual,
                    "payment_date": rec.payment_date,
                    "journal_id": rec.journal_id.id,
                }
                if rec.payment_method_line_id:
                    wizard_vals["payment_method_line_id"] = rec.payment_method_line_id.id

                pay_wizard = self.env["account.payment.register"].with_context(ctx).create(wizard_vals)
                action_res = pay_wizard.action_create_payments()

                payments = pay_wizard.payment_id
                if not payments and isinstance(action_res, dict):
                    if action_res.get("res_model") == "account.payment" and action_res.get("res_id"):
                        payments = self.env["account.payment"].browse(action_res["res_id"]).exists()

                if not payments:
                    raise UserError(_("No payment was created for invoice %s.") % invoice.display_name)

                payment = payments[0]
                if payment.state != "posted":
                    raise UserError(_("Created payment %s is not posted.") % payment.display_name)

                if hasattr(payment, "batch_invoice_id") and not payment.batch_invoice_id:
                    payment.batch_invoice_id = invoice.id

                ln.payment_id = payment.id
                ln.move_id = invoice.id

            if rec.name == "/":
                rec.name = rec.env["ir.sequence"].next_by_code("batch.payment") or f"BATCH/{rec.id}"
            rec.state = "validated"

    # ----------------------------------------------------------------
    # Export to Sage
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

                doc_no = ""
                if ln.move_id:
                    doc_no = ln.move_id.x_pastel_doc_no or ln.move_id.payment_reference or ln.move_id.name or ""

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

            _logger.info("Exporting BatchPayment %s to Sage with payload:\n%s",
                         rec.name, json.dumps(payload, indent=2, ensure_ascii=False))

            url = base.rstrip("/") + "/payments/batch"
            headers = {"x-api-key": key}
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=60)
                r.raise_for_status()
                data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            except Exception as e:
                raise UserError(_("Sage export failed: %s") % e)

            rec.exported_ref = data.get("batch_id") or data.get("reference") or rec.name
            rec.state = "exported"

    # ----------------------------------------------------------------
    # HARD SET invoice paid in DB if residual is 0
    # ----------------------------------------------------------------
    def _force_set_invoice_paid(self, invoice):
        """
        Hard-force account.move.payment_state to 'paid' when residual is 0.
        This is the most reliable way to reflect paid status immediately in the UI
        after custom reconciliation flows.
        """
        invoice = invoice.sudo().exists()
        if not invoice or invoice.state != "posted":
            return

        if float_is_zero(invoice.amount_residual, precision_rounding=invoice.currency_id.rounding):
            # Direct DB update (payment_state is stored)
            self.env.cr.execute(
                "UPDATE account_move SET payment_state = 'paid' WHERE id = %s",
                (invoice.id,)
            )
            self.env.flush_all()
            invoice.invalidate_recordset(["payment_state", "amount_residual"])

    # ----------------------------------------------------------------
    # Pay Batch (Reconcile and mark invoices paid)
    # ----------------------------------------------------------------


    def action_pay_batch(self):
        """
        Odoo 17 Pay Batch (strong version)
        1) Try to assign outstanding credits using invoice.js_assign_outstanding_line()
           by matching the invoice widget 'content' line ids to the payment move's AR/AP lines.
        2) If still not settled, fallback to direct reconcile on same account.
        3) Verify residual becomes 0.
        4) Mark batch as paid.
        """
        for rec in self:
            if rec.state not in ("validated", "exported"):
                raise UserError(_("Only Validated/Exported batches can be paid."))

            if not rec.line_ids:
                raise UserError(_("No lines to pay."))

            for ln in rec.line_ids:
                payment = ln.payment_id
                if not payment:
                    continue

                if payment.state != "posted":
                    raise UserError(_("Payment %s must be posted before paying the batch.") % payment.display_name)

                if not payment.move_id:
                    raise UserError(_("Payment %s has no journal entry (move_id).") % payment.display_name)

                # ---- Find invoice ----
                invoice = ln.move_id or (ln.move_line_id.move_id if ln.move_line_id else False)
                if not invoice and getattr(payment, "batch_invoice_id", False):
                    invoice = payment.batch_invoice_id
                    ln.move_id = invoice.id

                if not invoice:
                    raise UserError(_("Payment %s has no linked invoice.") % payment.display_name)

                if invoice.state != "posted":
                    continue

                # ---- Partner safety (commercial partner) ----
                inv_partner = invoice.partner_id.commercial_partner_id
                pay_partner = payment.partner_id.commercial_partner_id
                if inv_partner != pay_partner:
                    raise UserError(_(
                        "Partner mismatch:\nInvoice %(inv)s partner: %(ip)s\nPayment %(pay)s partner: %(pp)s"
                    ) % {
                                        "inv": invoice.display_name,
                                        "ip": inv_partner.display_name,
                                        "pay": payment.display_name,
                                        "pp": pay_partner.display_name,
                                    })

                # ---- Open invoice AR/AP lines ----
                inv_open = invoice.line_ids.filtered(lambda l:
                                                     l.account_id.account_type in (
                                                     "asset_receivable", "liability_payable")
                                                     and not l.reconciled
                                                     )

                # If invoice already settled (sometimes UI is stale)
                invoice.invalidate_recordset(["amount_residual", "payment_state"])
                if float_is_zero(invoice.amount_residual, precision_rounding=invoice.currency_id.rounding):
                    continue

                # ---- Payment AR/AP lines (these are the outstanding credit/debit lines) ----
                pay_open = payment.move_id.line_ids.filtered(lambda l:
                                                             l.account_id.account_type in (
                                                             "asset_receivable", "liability_payable")
                                                             and not l.reconciled
                                                             )
                pay_open_ids = set(pay_open.ids)

                if not pay_open:
                    # Nothing to assign/reconcile from payment side
                    raise UserError(
                        _("Payment %s has no outstanding AR/AP lines (already reconciled?).") % payment.display_name)

                # ============================================================
                # 1) Try APPLY OUTSTANDING lines via widget (UI-equivalent)
                #    Match widget content line ids to payment's open AR/AP line ids
                # ============================================================
                if hasattr(invoice, "invoice_outstanding_credits_debits_widget") and hasattr(invoice,
                                                                                             "js_assign_outstanding_line"):
                    widget_raw = invoice.invoice_outstanding_credits_debits_widget
                    widget = {}
                    if widget_raw:
                        if isinstance(widget_raw, str):
                            try:
                                widget = json.loads(widget_raw or "{}")
                            except Exception:
                                widget = {}
                        elif isinstance(widget_raw, dict):
                            widget = widget_raw

                    content = widget.get("content") or []
                    # collect widget line ids that are actually from this payment move
                    widget_line_ids = []
                    for item in content:
                        wid = item.get("id")
                        if wid and wid in pay_open_ids:
                            widget_line_ids.append(wid)

                    # apply all matches (safe: can be partials)
                    for wid in widget_line_ids:
                        invoice.js_assign_outstanding_line(wid)

                # Refresh after assigning
                self.env.flush_all()
                invoice.invalidate_recordset(["amount_residual", "payment_state"])
                invoice = self.env["account.move"].browse(invoice.id)

                # If settled now, continue
                if float_is_zero(invoice.amount_residual, precision_rounding=invoice.currency_id.rounding):
                    continue

                # ============================================================
                # 2) Fallback: DIRECT RECONCILE (same account) if widget didn’t settle
                # ============================================================
                inv_open = invoice.line_ids.filtered(lambda l:
                                                     l.account_id.account_type in (
                                                     "asset_receivable", "liability_payable")
                                                     and not l.reconciled
                                                     )
                pay_open = payment.move_id.line_ids.filtered(lambda l:
                                                             l.account_id.account_type in (
                                                             "asset_receivable", "liability_payable")
                                                             and not l.reconciled
                                                             )

                # reconcile per account
                for acc in inv_open.mapped("account_id"):
                    inv_acc_lines = inv_open.filtered(lambda l: l.account_id == acc and not l.reconciled)
                    pay_acc_lines = pay_open.filtered(lambda l: l.account_id == acc and not l.reconciled)
                    if inv_acc_lines and pay_acc_lines:
                        (inv_acc_lines + pay_acc_lines).reconcile()

                # Final refresh & verify
                self.env.flush_all()
                invoice.invalidate_recordset(["amount_residual", "payment_state"])
                invoice = self.env["account.move"].browse(invoice.id)

                if not float_is_zero(invoice.amount_residual, precision_rounding=invoice.currency_id.rounding):
                    # Give HARD diagnostics so we stop “trying random”
                    inv_acc = invoice.line_ids.filtered(
                        lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable"))[:1].account_id
                    pay_acc = payment.move_id.line_ids.filtered(
                        lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable"))[:1].account_id

                    raise UserError(_(
                        "Invoice %(inv)s is still not paid after applying payment %(pay)s.\n\n"
                        "Residual remaining: %(res)s\n"
                        "Invoice AR/AP account: %(inv_acc)s\n"
                        "Payment AR/AP account: %(pay_acc)s\n"
                        "Payment State: %(pst)s\n\n"
                        "This means the invoice and payment are NOT reconciling (different AR/AP line, "
                        "or custom module blocking reconciliation/payment_state)."
                    ) % {
                                        "inv": invoice.display_name,
                                        "pay": payment.display_name,
                                        "res": invoice.amount_residual,
                                        "inv_acc": inv_acc.display_name if inv_acc else "N/A",
                                        "pay_acc": pay_acc.display_name if pay_acc else "N/A",
                                        "pst": invoice.payment_state,
                                    })

            # Mark batch paid
            rec.state = "paid"

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
                and (not rec.payment_method_line_id or ln.payment_id.payment_method_line_id == rec.payment_method_line_id)
                and (
                    rec.partner_type != "customer"
                    or not rec.partner_id
                    or ln.payment_id.partner_id == rec.partner_id
                )
            )
            if len(to_keep) != len(rec.line_ids):
                rec.line_ids = [(6, 0, to_keep.ids)]


# -------------------------------------------------------------------
# Lines
# -------------------------------------------------------------------
class BatchPaymentLine(models.Model):
    _name = "batch.payment.line"
    _description = "Batch Payment Line"
    _order = "id asc"

    batch_id = fields.Many2one("batch.payment", required=True, ondelete="cascade")
    payment_id = fields.Many2one("account.payment", string="Payment")

    number = fields.Char(related="payment_id.name", store=True)
    date = fields.Date(related="payment_id.date", store=True)
    journal_id = fields.Many2one("account.journal", related="payment_id.journal_id", store=True)
    company_id = fields.Many2one("res.company", related="payment_id.company_id", store=True)
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        related="payment_id.payment_method_line_id",
        store=True,
    )
    partner_id = fields.Many2one("res.partner", related="payment_id.partner_id", store=True, string="Customer/Supplier")
    status = fields.Selection(related="payment_id.state", store=True, string="Status")

    amount = fields.Monetary(currency_field="currency_id", compute="_compute_amount_from_payment", store=True)
    currency_id = fields.Many2one(related="batch_id.currency_id", store=True)

    move_id = fields.Many2one("account.move", string="Invoice/Bill")
    move_line_id = fields.Many2one("account.move.line", string="Open Item")
    communication = fields.Char()

    @api.depends("payment_id.amount", "payment_id.currency_id")
    def _compute_amount_from_payment(self):
        for ln in self:
            ln.amount = abs(ln.payment_id.amount) if ln.payment_id else (ln.amount or 0.0)

    def _check_payment_matches_header(self):
        """
        Enforce that chosen payment matches the batch header filters.
        """
        for line in self:
            pay = line.payment_id
            batch = line.batch_id
            if not pay or not batch:
                continue

            if batch.journal_id and pay.journal_id != batch.journal_id:
                raise ValidationError(
                    _("Payment %(p)s journal (%(pj)s) doesn't match batch journal (%(bj)s).") % {
                        "p": pay.display_name,
                        "pj": pay.journal_id.display_name or pay.journal_id.name,
                        "bj": batch.journal_id.display_name or batch.journal_id.name,
                    }
                )

            if batch.company_id and pay.company_id != batch.company_id:
                raise ValidationError(
                    _("Payment %(p)s company (%(pc)s) doesn't match batch company (%(bc)s).") % {
                        "p": pay.display_name,
                        "pc": pay.company_id.display_name or pay.company_id.name,
                        "bc": batch.company_id.display_name or batch.company_id.name,
                    }
                )

            if pay.state != "posted":
                raise ValidationError(
                    _("Payment %(p)s is not posted (state: %(st)s).") % {
                        "p": pay.display_name,
                        "st": pay.state,
                    }
                )

            if hasattr(batch, "payment_method_line_id") and batch.payment_method_line_id:
                if pay.payment_method_line_id != batch.payment_method_line_id:
                    raise ValidationError(
                        _("Payment %(p)s method (%(pm)s) doesn't match batch method (%(bm)s).") % {
                            "p": pay.display_name,
                            "pm": pay.payment_method_line_id.display_name or pay.payment_method_line_id.name,
                            "bm": batch.payment_method_line_id.display_name or batch.payment_method_line_id.name,
                        }
                    )


# # -*- coding: utf-8 -*-
# from odoo import api, fields, models, _
# from odoo.exceptions import ValidationError, UserError
# from odoo.tools.float_utils import float_is_zero
# import requests
# import logging
# import json
#
# _logger = logging.getLogger(__name__)
#
#
# # -------------------------------------------------------------------
# # Settings
# # -------------------------------------------------------------------
# class ResConfigSettings(models.TransientModel):
#     _inherit = "res.config.settings"
#
#     pastel_bridge_base = fields.Char(string="Pastel Bridge Base URL")
#     pastel_bridge_key = fields.Char(string="Pastel Bridge API Key")
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
# # -------------------------------------------------------------------
# # Batch Payment
# # -------------------------------------------------------------------
# class BatchPayment(models.Model):
#     _name = "batch.payment"
#     _description = "Batch Payment"
#     _inherit = ["mail.thread", "mail.activity.mixin"]
#     _order = "id desc"
#
#     name = fields.Char(default="/", readonly=True)
#
#     state = fields.Selection([
#         ("draft", "Draft"),
#         ("validated", "Validated"),
#         ("exported", "Exported"),
#         ("paid", "Paid"),
#     ], default="draft", tracking=True)
#
#     payment_date = fields.Date(required=True, default=fields.Date.context_today)
#
#     partner_type = fields.Selection(
#         [("customer", "Customer"), ("supplier", "Supplier")],
#         required=True,
#         default="customer",
#     )
#
#     partner_id = fields.Many2one(
#         "res.partner",
#         string="Customer",
#         domain="[('customer_rank','>',0)]",
#         help="Filter posted payments by this customer.",
#     )
#
#     journal_id = fields.Many2one(
#         "account.journal",
#         required=True,
#         domain="[('type','in',['bank','cash'])]",
#     )
#
#     payment_method_line_id = fields.Many2one(
#         "account.payment.method.line",
#         string="Payment Method",
#         domain="[('journal_id','=',journal_id)]",
#         help="Filters posted payments by this method.",
#     )
#
#     currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id)
#     company_id = fields.Many2one("res.company", default=lambda s: s.env.company, required=True)
#
#     line_ids = fields.One2many("batch.payment.line", "batch_id", string="Lines")
#
#     amount_total = fields.Monetary(currency_field="currency_id", compute="_compute_amounts", store=True)
#     exported_ref = fields.Char("Export Reference", readonly=True)
#     note = fields.Text()
#
#     @api.depends("line_ids.amount")
#     def _compute_amounts(self):
#         for rec in self:
#             rec.amount_total = sum(rec.line_ids.mapped("amount"))
#
#     # ----------------------------------------------------------------
#     # Load open items (unpaid AR/AP move lines)
#     # ----------------------------------------------------------------
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
#             residual = aml.amount_residual if aml.currency_id != aml.company_currency_id else aml.amount_residual
#             amount = abs(residual)
#             if amount <= 0:
#                 continue
#             new_lines.append((0, 0, {
#                 "move_id": aml.move_id.id,
#                 "move_line_id": aml.id,
#                 "communication": aml.move_id.name or aml.ref or "",
#                 "amount": amount,
#             }))
#
#         if new_lines:
#             self.write({"line_ids": new_lines})
#
#     # ----------------------------------------------------------------
#     # Load posted payments (and auto-link invoice using payment.batch_invoice_id)
#     # ----------------------------------------------------------------
#     def action_load_posted_payments(self):
#         self.ensure_one()
#         if self.state != "draft":
#             raise UserError(_("Only draft batches can load payments"))
#
#         domain = [
#             ("state", "=", "posted"),
#             ("company_id", "=", self.company_id.id),
#             ("journal_id", "=", self.journal_id.id),
#         ]
#
#         if self.partner_type == "customer":
#             domain.append(("partner_type", "=", "customer"))
#             if self.partner_id:
#                 domain.append(("partner_id", "=", self.partner_id.id))
#         else:
#             domain.append(("partner_type", "=", "supplier"))
#             if self.partner_id:
#                 domain.append(("partner_id", "=", self.partner_id.id))
#
#         if self.payment_method_line_id:
#             domain.append(("payment_method_line_id", "=", self.payment_method_line_id.id))
#
#         payments = self.env["account.payment"].search(domain, order="date asc", limit=500)
#         if not payments:
#             raise UserError(_("No posted payments found for the selected filters."))
#
#         existing_payment_ids = set(self.line_ids.mapped("payment_id").ids)
#         to_add = []
#         for p in payments:
#             if p.id in existing_payment_ids:
#                 continue
#
#             # IMPORTANT: link the invoice if payment was created via batch-mode register
#             move_id = p.batch_invoice_id.id if getattr(p, "batch_invoice_id", False) else False
#
#             to_add.append((0, 0, {
#                 "payment_id": p.id,
#                 "communication": p.ref or p.name or "",
#                 "amount": abs(p.amount),
#                 "move_id": move_id,
#             }))
#
#         if not to_add:
#             raise UserError(_("All matching posted payments are already in this batch."))
#
#         self.write({"line_ids": to_add})
#
#
#     def action_validate(self):
#         for rec in self:
#             if rec.state != "draft":
#                 raise UserError(_("Only draft batches can be validated."))
#             if not rec.line_ids:
#                 raise UserError(_("No lines."))
#
#             for ln in rec.line_ids:
#                 # ---------------------------------------------------------
#                 # A) If already linked to a posted payment, keep it
#                 # ---------------------------------------------------------
#                 if ln.payment_id:
#                     if ln.payment_id.state != "posted":
#                         raise UserError(_("Payment %s is not posted.") % ln.payment_id.display_name)
#
#                     # backfill invoice link if payment has batch_invoice_id
#                     if not ln.move_id and getattr(ln.payment_id, "batch_invoice_id", False):
#                         ln.move_id = ln.payment_id.batch_invoice_id.id
#                     continue
#
#                 # ---------------------------------------------------------
#                 # B) Otherwise: create payment using official wizard
#                 # ---------------------------------------------------------
#                 invoice = ln.move_id or (ln.move_line_id.move_id if ln.move_line_id else False)
#                 if not invoice:
#                     raise UserError(_("Line has no invoice/open item to create a payment from."))
#
#                 if invoice.state != "posted":
#                     raise UserError(_("Invoice %s must be posted before validating the batch.") % invoice.display_name)
#
#                 # Create the payment register wizard in the same way as UI button
#                 ctx = dict(self.env.context or {})
#                 ctx.update({
#                     "active_model": "account.move",
#                     "active_ids": [invoice.id],
#                     "active_id": invoice.id,
#                     # ✅ very important: do NOT auto reconcile in batch mode
#                     "batch_skip_reconcile": True,
#                 })
#
#                 wizard_vals = {
#                     "amount": ln.amount or invoice.amount_residual,
#                     "payment_date": rec.payment_date,
#                     "journal_id": rec.journal_id.id,
#                 }
#
#                 # only set method line if provided
#                 if rec.payment_method_line_id:
#                     wizard_vals["payment_method_line_id"] = rec.payment_method_line_id.id
#
#                 pay_wizard = self.env["account.payment.register"].with_context(ctx).create(wizard_vals)
#
#                 # this creates & posts the payment; our override sets batch_invoice_id
#                 action_res = pay_wizard.action_create_payments()
#
#                 # get created payment(s)
#                 payments = pay_wizard.payment_id
#                 if not payments and isinstance(action_res, dict):
#                     if action_res.get("res_model") == "account.payment" and action_res.get("res_id"):
#                         payments = self.env["account.payment"].browse(action_res["res_id"]).exists()
#
#                 if not payments:
#                     raise UserError(_("No payment was created for invoice %s.") % invoice.display_name)
#
#                 # link the first payment (normally 1)
#                 payment = payments[0]
#                 if payment.state != "posted":
#                     raise UserError(_("Created payment %s is not posted.") % payment.display_name)
#
#                 # ensure invoice link is stored
#                 if hasattr(payment, "batch_invoice_id") and not payment.batch_invoice_id:
#                     payment.batch_invoice_id = invoice.id
#
#                 ln.payment_id = payment.id
#                 ln.move_id = invoice.id
#
#             if rec.name == "/":
#                 rec.name = rec.env["ir.sequence"].next_by_code("batch.payment") or f"BATCH/{rec.id}"
#             rec.state = "validated"
#
#     # ----------------------------------------------------------------
#     # Export to Sage
#     # ----------------------------------------------------------------
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
#                 partner = ln.partner_id
#                 partner_code = (getattr(partner, "x_pastel_code", "") or "").strip() or \
#                                (partner.ref or partner.name or "").strip()
#
#                 doc_no = ""
#                 if ln.move_id:
#                     doc_no = ln.move_id.x_pastel_doc_no or ln.move_id.payment_reference or ln.move_id.name or ""
#
#                 lines.append({
#                     "partner_code": partner_code,
#                     "invoice_doc_no": doc_no or None,
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
#             _logger.info("Exporting BatchPayment %s to Sage with payload:\n%s",
#                          rec.name, json.dumps(payload, indent=2, ensure_ascii=False))
#
#             url = base.rstrip("/") + "/payments/batch"
#             headers = {"x-api-key": key}
#             try:
#                 r = requests.post(url, json=payload, headers=headers, timeout=60)
#                 r.raise_for_status()
#                 data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
#             except Exception as e:
#                 raise UserError(_("Sage export failed: %s") % e)
#
#             rec.exported_ref = data.get("batch_id") or data.get("reference") or rec.name
#             rec.state = "exported"
#
#     def _force_invoice_paid_state_refresh(self, invoice):
#         """Force Odoo to recompute & store payment_state when we reconciled in custom code."""
#         invoice = invoice.sudo().exists()
#         if not invoice:
#             return
#
#         # Ensure DB is flushed (reconcile created/updated partial/full reconcile records)
#         self.env.flush_all()
#
#         # Reload invoice to avoid cache weirdness
#         invoice = self.env["account.move"].browse(invoice.id)
#
#         # If residual is 0, payment_state should become paid (unless Odoo considers it in_payment)
#         # We force recompute of stored field payment_state.
#         field = invoice._fields.get("payment_state")
#         if field:
#             self.env.add_to_compute(field, invoice)
#             self.env.flush_all()
#
#         invoice.invalidate_recordset(["amount_residual", "payment_state"])
#         invoice = self.env["account.move"].browse(invoice.id)
#
#         # If still not paid but residual is 0, force one more recompute pass
#         # if float_is_zero(invoice.amount_residual, precision_rounding=invoice.currency_id.rounding):
#         #     if field:
#         #         self.env.add_to_compute(field, invoice)
#         #         self.env.flush_all()
#         #         invoice.invalidate_recordset(["payment_state"])
#
#         # If residual is zero, invoice IS settled. payment_state must become paid after recompute.
#         if float_is_zero(invoice.amount_residual, precision_rounding=invoice.currency_id.rounding):
#             # After forcing recompute, it should now be paid/in_payment depending on config
#             if invoice.payment_state not in ("paid", "in_payment"):
#                 raise UserError(_(
#                     "Residual is 0.0 but payment_state is still %(ps)s.\n"
#                     "This indicates a custom override of payment_state compute OR stale UI.\n"
#                     "Try hard refresh (Ctrl+F5) or check custom modules overriding account.move."
#                 ) % {"ps": invoice.payment_state})
#         else:
#             raise UserError(_("Residual is still not zero: %s") % invoice.amount_residual)
#
#     def _force_set_invoice_paid(self, invoice):
#         """
#         Hard-force payment_state to 'paid' when residual is 0.
#         Needed because payment_state is stored and may not recompute instantly in custom reconciliation flows.
#         """
#         invoice = invoice.sudo().exists()
#         if not invoice:
#             return
#
#         # Only for posted invoices/bills
#         if invoice.state != "posted":
#             return
#
#         # If residual is truly zero -> mark paid in DB
#         if float_is_zero(invoice.amount_residual, precision_rounding=invoice.currency_id.rounding):
#             self.env.cr.execute(
#                 """
#                 UPDATE account_move
#                    SET payment_state = 'paid'
#                  WHERE id = %s
#                 """,
#                 (invoice.id,)
#             )
#             # Flush and refresh cache so UI sees the change
#             self.env.flush_all()
#             invoice.invalidate_recordset(["payment_state", "amount_residual"])
#
#     # ----------------------------------------------------------------
#     # Pay Batch (Reconcile and mark invoices paid)
#     # ----------------------------------------------------------------
#     def action_pay_batch(self):
#         """
#         Pay Batch:
#         - If payment AR/AP account matches invoice AR/AP account: reconcile directly.
#         - If they differ: create a reclass journal entry (general journal) then reconcile.
#
#         After reconciliation:
#         - If residual == 0, hard-force invoice.payment_state = 'paid' so UI updates immediately.
#         """
#         for rec in self:
#             if rec.state not in ("validated", "exported"):
#                 raise UserError(_("Only Validated/Exported batches can be paid."))
#
#             if not rec.line_ids:
#                 raise UserError(_("No lines to pay."))
#
#             general_journal = self.env["account.journal"].search(
#                 [("type", "=", "general"), ("company_id", "=", rec.company_id.id)],
#                 limit=1
#             )
#             if not general_journal:
#                 raise UserError(
#                     _("No General Journal found in company %s (type='general').") % rec.company_id.display_name)
#
#             for ln in rec.line_ids:
#                 payment = ln.payment_id
#                 if not payment:
#                     continue
#
#                 if payment.state != "posted":
#                     raise UserError(_("Payment %s must be posted before paying the batch.") % payment.display_name)
#
#                 # --- Find invoice ---
#                 invoice = ln.move_id or (ln.move_line_id.move_id if ln.move_line_id else False)
#                 if not invoice and getattr(payment, "batch_invoice_id", False):
#                     invoice = payment.batch_invoice_id
#                     ln.move_id = invoice.id
#
#                 if not invoice:
#                     raise UserError(
#                         _("Payment %s has no linked invoice (move_id/batch_invoice_id empty).") % payment.display_name)
#
#                 if invoice.state != "posted":
#                     continue
#
#                 if not payment.move_id:
#                     raise UserError(_("Payment %s has no journal entry (move_id).") % payment.display_name)
#
#                 # --- Invoice open AR/AP line(s) ---
#                 inv_lines = invoice.line_ids.filtered(lambda l:
#                                                       l.account_id.account_type in (
#                                                       "asset_receivable", "liability_payable") and not l.reconciled
#                                                       )
#                 if not inv_lines:
#                     # already paid or nothing to reconcile
#                     self._force_set_invoice_paid(invoice)
#                     continue
#
#                 # --- Payment open AR/AP line(s) ---
#                 pay_lines = payment.move_id.line_ids.filtered(lambda l:
#                                                               l.account_id.account_type in ("asset_receivable",
#                                                                                             "liability_payable") and not l.reconciled
#                                                               )
#                 if not pay_lines:
#                     raise UserError(_("Payment %s has no outstanding AR/AP line to reconcile.") % payment.display_name)
#
#                 inv_line = inv_lines[:1]
#                 pay_line = pay_lines[:1]
#
#                 # partner safety
#                 if invoice.partner_id and pay_line.partner_id and invoice.partner_id != pay_line.partner_id:
#                     raise UserError(_(
#                         "Partner mismatch:\nInvoice %(inv)s partner: %(ip)s\nPayment %(pay)s partner line: %(pp)s"
#                     ) % {
#                                         "inv": invoice.display_name,
#                                         "ip": invoice.partner_id.display_name,
#                                         "pay": payment.display_name,
#                                         "pp": pay_line.partner_id.display_name,
#                                     })
#
#                 inv_acc = inv_line.account_id
#                 pay_acc = pay_line.account_id
#
#                 amt = min(abs(inv_line.amount_residual), abs(pay_line.amount_residual))
#                 if amt <= 0:
#                     self._force_set_invoice_paid(invoice)
#                     continue
#
#                 # --- Case 1: Same account => reconcile directly ---
#                 if inv_acc.id == pay_acc.id:
#                     (inv_line + pay_line).reconcile()
#                 else:
#                     # --- Case 2: Different accounts => reclass then reconcile ---
#                     def _sign(x):
#                         return 1 if x > 0 else (-1 if x < 0 else 0)
#
#                     s_pay = _sign(pay_line.balance)
#                     s_inv = _sign(inv_line.balance)
#                     if s_pay == 0 or s_inv == 0:
#                         raise UserError(_(
#                             "Cannot determine sign for reconciliation.\n"
#                             "Payment line balance=%(pb)s, Invoice line balance=%(ib)s"
#                         ) % {"pb": pay_line.balance, "ib": inv_line.balance})
#
#                     bal_pay = -s_pay * amt
#                     bal_inv = -s_inv * amt
#
#                     if round(bal_pay + bal_inv, 2) != 0.0:
#                         raise UserError(_(
#                             "Accounts differ AND signs are not opposite, cannot auto-reclass safely.\n"
#                             "Invoice sign=%(si)s, Payment sign=%(sp)s.\n"
#                             "Invoice acc=%(ia)s, Payment acc=%(pa)s"
#                         ) % {
#                                             "si": s_inv,
#                                             "sp": s_pay,
#                                             "ia": inv_acc.display_name,
#                                             "pa": pay_acc.display_name,
#                                         })
#
#                     def _dc(balance):
#                         if balance > 0:
#                             return (balance, 0.0)
#                         return (0.0, -balance)
#
#                     d1, c1 = _dc(bal_pay)
#                     d2, c2 = _dc(bal_inv)
#
#                     reclass_move = self.env["account.move"].create({
#                         "move_type": "entry",
#                         "date": rec.payment_date,
#                         "journal_id": general_journal.id,
#                         "company_id": rec.company_id.id,
#                         "ref": "Batch Reclass %s / %s" % (rec.name, payment.name),
#                         "line_ids": [
#                             (0, 0, {
#                                 "name": "Reclass for %s" % payment.name,
#                                 "account_id": pay_acc.id,
#                                 "partner_id": invoice.partner_id.id,
#                                 "debit": d1,
#                                 "credit": c1,
#                             }),
#                             (0, 0, {
#                                 "name": "Reclass for %s" % invoice.name,
#                                 "account_id": inv_acc.id,
#                                 "partner_id": invoice.partner_id.id,
#                                 "debit": d2,
#                                 "credit": c2,
#                             }),
#                         ],
#                     })
#                     reclass_move.action_post()
#
#                     reclass_pay_line = reclass_move.line_ids.filtered(
#                         lambda l: l.account_id.id == pay_acc.id and not l.reconciled
#                     )[:1]
#                     reclass_inv_line = reclass_move.line_ids.filtered(
#                         lambda l: l.account_id.id == inv_acc.id and not l.reconciled
#                     )[:1]
#                     if not reclass_pay_line or not reclass_inv_line:
#                         raise UserError(_("Reclass journal entry lines not found for reconciliation."))
#
#                     (pay_line + reclass_pay_line).reconcile()
#                     (inv_line + reclass_inv_line).reconcile()
#
#                 # --- FORCE paid state when residual is zero ---
#                 self.env.flush_all()
#                 invoice.invalidate_recordset(["amount_residual", "payment_state"])
#                 invoice = self.env["account.move"].browse(invoice.id)
#
#                 # This is the key: if settled, hard-set paid so UI updates
#                 self._force_set_invoice_paid(invoice)
#
#             # Mark batch as paid
#             if "paid" in dict(rec._fields["state"].selection or []):
#                 rec.state = "paid"
#
#     @api.onchange("journal_id", "payment_method_line_id", "partner_id", "company_id")
#     def _onchange_filters_prune_lines(self):
#         for rec in self:
#             if not rec.line_ids:
#                 continue
#             to_keep = rec.line_ids.filtered(lambda ln:
#                 ln.payment_id
#                 and ln.payment_id.state == "posted"
#                 and (not rec.journal_id or ln.payment_id.journal_id == rec.journal_id)
#                 and (not rec.company_id or ln.payment_id.company_id == rec.company_id)
#                 and (not rec.payment_method_line_id or ln.payment_id.payment_method_line_id == rec.payment_method_line_id)
#                 and (
#                     rec.partner_type != "customer"
#                     or not rec.partner_id
#                     or ln.payment_id.partner_id == rec.partner_id
#                 )
#             )
#             if len(to_keep) != len(rec.line_ids):
#                 rec.line_ids = [(6, 0, to_keep.ids)]
#
#
# # -------------------------------------------------------------------
# # Lines
# # -------------------------------------------------------------------
# class BatchPaymentLine(models.Model):
#     _name = "batch.payment.line"
#     _description = "Batch Payment Line"
#     _order = "id asc"
#
#     batch_id = fields.Many2one("batch.payment", required=True, ondelete="cascade")
#     payment_id = fields.Many2one("account.payment", string="Payment")
#
#     number = fields.Char(related="payment_id.name", store=True)
#     date = fields.Date(related="payment_id.date", store=True)
#     journal_id = fields.Many2one("account.journal", related="payment_id.journal_id", store=True)
#     company_id = fields.Many2one("res.company", related="payment_id.company_id", store=True)
#     payment_method_line_id = fields.Many2one(
#         "account.payment.method.line",
#         related="payment_id.payment_method_line_id",
#         store=True,
#     )
#     partner_id = fields.Many2one("res.partner", related="payment_id.partner_id", store=True, string="Customer/Supplier")
#     status = fields.Selection(related="payment_id.state", store=True, string="Status")
#
#     amount = fields.Monetary(currency_field="currency_id", compute="_compute_amount_from_payment", store=True)
#     currency_id = fields.Many2one(related="batch_id.currency_id", store=True)
#
#     move_id = fields.Many2one("account.move", string="Invoice/Bill")
#     move_line_id = fields.Many2one("account.move.line", string="Open Item")
#     communication = fields.Char()
#
#     @api.depends("payment_id.amount", "payment_id.currency_id")
#     def _compute_amount_from_payment(self):
#         for ln in self:
#             ln.amount = abs(ln.payment_id.amount) if ln.payment_id else (ln.amount or 0.0)
#
#     def _check_payment_matches_header(self):
#         """
#         Enforce that chosen payment matches the batch header filters.
#         """
#         for line in self:
#             pay = line.payment_id
#             batch = line.batch_id
#             if not pay or not batch:
#                 continue
#
#             if batch.journal_id and pay.journal_id != batch.journal_id:
#                 raise ValidationError(
#                     _("Payment %(p)s journal (%(pj)s) doesn't match batch journal (%(bj)s).") % {
#                         "p": pay.display_name,
#                         "pj": pay.journal_id.display_name or pay.journal_id.name,
#                         "bj": batch.journal_id.display_name or batch.journal_id.name,
#                     }
#                 )
#
#             if batch.company_id and pay.company_id != batch.company_id:
#                 raise ValidationError(
#                     _("Payment %(p)s company (%(pc)s) doesn't match batch company (%(bc)s).") % {
#                         "p": pay.display_name,
#                         "pc": pay.company_id.display_name or pay.company_id.name,
#                         "bc": batch.company_id.display_name or batch.company_id.name,
#                     }
#                 )
#
#             if pay.state != "posted":
#                 raise ValidationError(
#                     _("Payment %(p)s is not posted (state: %(st)s).") % {
#                         "p": pay.display_name,
#                         "st": pay.state,
#                     }
#                 )
#
#             if hasattr(batch, "payment_method_line_id") and batch.payment_method_line_id:
#                 if pay.payment_method_line_id != batch.payment_method_line_id:
#                     raise ValidationError(
#                         _("Payment %(p)s method (%(pm)s) doesn't match batch method (%(bm)s).") % {
#                             "p": pay.display_name,
#                             "pm": pay.payment_method_line_id.display_name or pay.payment_method_line_id.name,
#                             "bm": batch.payment_method_line_id.display_name or batch.payment_method_line_id.name,
#                         }
#                     )
#

# from odoo import api, fields, models, _
# from odoo.exceptions import ValidationError, UserError
# import requests
# import logging
# import json
# _logger = logging.getLogger(__name__)
# # -------------------------------------------------------------------
# # Settings (unchanged)
# # -------------------------------------------------------------------
# class ResConfigSettings(models.TransientModel):
#     _inherit = "res.config.settings"
#
#     pastel_bridge_base = fields.Char(string="Pastel Bridge Base URL")
#     pastel_bridge_key = fields.Char(string="Pastel Bridge API Key")
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
# # -------------------------------------------------------------------
# # Batch Payment
# # -------------------------------------------------------------------
# class BatchPayment(models.Model):
#     _name = "batch.payment"
#     _description = "Batch Payment"
#     _inherit = ['mail.thread', 'mail.activity.mixin']
#     _order = "id desc"
#
#     # Header
#     name = fields.Char(default="/", readonly=True)
#     state = fields.Selection([
#         ("draft", "Draft"),
#         ("validated", "Validated"),
#         ("exported", "Exported"),
#         ("paid", "Paid"),
#     ], default="draft", tracking=True)
#
#     payment_date = fields.Date(required=True, default=fields.Date.context_today)
#
#     partner_type = fields.Selection(
#         [("customer", "Customer"), ("supplier", "Supplier")],
#         required=True, default="customer"
#     )
#
#     # NEW: Header-level customer selector (requested)
#     partner_id = fields.Many2one(
#         "res.partner",
#         string="Customer",
#         domain="[('customer_rank','>',0)]",
#         help="Filter posted payments by this customer."
#     )
#
#     journal_id = fields.Many2one("account.journal", required=True, domain="[('type','in',['bank','cash'])]")
#
#     # NEW: Payment method line (journal-bound)
#     payment_method_line_id = fields.Many2one(
#         "account.payment.method.line",
#         string="Payment Method",
#         domain="[('journal_id','=',journal_id)]",
#         help="Filters posted payments by this method."
#     )
#
#     currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id)
#     company_id  = fields.Many2one("res.company", default=lambda s: s.env.company, required=True)
#
#     line_ids = fields.One2many("batch.payment.line", "batch_id", string="Lines")
#
#     amount_total = fields.Monetary(currency_field="currency_id", compute="_compute_amounts", store=True)
#     exported_ref = fields.Char("Export Reference", readonly=True)
#     note = fields.Text()
#
#     @api.depends("line_ids.amount")
#     def _compute_amounts(self):
#         for rec in self:
#             rec.amount_total = sum(rec.line_ids.mapped("amount"))
#
#     # ----------------------------------------------------------------
#     # EXISTING: Load open items (kept as-is for your previous flow)
#     # ----------------------------------------------------------------
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
#                 "move_id": aml.move_id.id,
#                 "move_line_id": aml.id,
#                 "communication": aml.move_id.name or aml.ref or "",
#                 "amount": amount,
#             }))
#         if new_lines:
#             self.write({"line_ids": new_lines})
#
#     # ----------------------------------------------------------------
#     # NEW: Load posted account.payment filtered by Customer/Journal/Method
#     # ----------------------------------------------------------------
#     def action_load_posted_payments(self):
#         self.ensure_one()
#         if self.state != "draft":
#             raise UserError(_("Only draft batches can load payments"))
#
#         domain = [
#             ("state", "=", "posted"),
#             ("company_id", "=", self.company_id.id),
#             ("journal_id", "=", self.journal_id.id),
#         ]
#         # Infer inbound/outbound by partner_type for clarity
#         # (Not strictly required to search, but documents intent)
#         if self.partner_type == "customer":
#             domain.append(("partner_type", "=", "customer"))
#             if self.partner_id:
#                 domain.append(("partner_id", "=", self.partner_id.id))
#         else:
#             domain.append(("partner_type", "=", "supplier"))
#             if self.partner_id:
#                 domain.append(("partner_id", "=", self.partner_id.id))
#
#         if self.payment_method_line_id:
#             domain.append(("payment_method_line_id", "=", self.payment_method_line_id.id))
#
#         payments = self.env["account.payment"].search(domain, order="date asc", limit=500)
#         if not payments:
#             raise UserError(_("No posted payments found for the selected filters."))
#
#         # Avoid duplicates in the batch
#         existing_payment_ids = set(self.line_ids.mapped("payment_id").ids)
#         to_add = []
#         for p in payments:
#             if p.id in existing_payment_ids:
#                 continue
#             to_add.append((0, 0, {
#                 "payment_id": p.id,
#                 "communication": p.ref or p.name or "",
#                 "amount": abs(p.amount),
#             }))
#
#         if not to_add:
#             raise UserError(_("All matching posted payments are already in this batch."))
#
#         self.write({"line_ids": to_add})
#
#     # ----------------------------------------------------------------
#     # VALIDATE: now just ensures lines are valid (no creation needed)
#     # For the “posted payment” flow, we don’t create new account.payment
#     # ----------------------------------------------------------------
#     def action_validate(self):
#         for rec in self:
#             if rec.state != "draft":
#                 raise UserError(_("Only draft batches can be validated."))
#             if not rec.line_ids:
#                 raise UserError(_("No lines."))
#
#             # If a line is linked to a posted payment, accept it.
#             # If not linked, it came from the "open items" loader; create & post a payment for it.
#             for ln in rec.line_ids:
#                 if ln.payment_id:
#                     if ln.payment_id.state != "posted":
#                         raise UserError(_("Payment %s is not posted.") % (ln.payment_id.display_name,))
#                     continue
#
#                 # Fallback: create payments for open-item lines (your old flow)
#                 pay_vals = {
#                     "date": rec.payment_date,
#                     "journal_id": rec.journal_id.id,
#                     "currency_id": rec.currency_id.id or rec.company_id.currency_id.id,
#                     "amount": ln.amount,
#                     "ref": ln.communication or rec.name or "",
#                     "partner_id": ln.partner_id.id if ln.partner_id else False,
#                     "payment_type": "inbound" if rec.partner_type == "customer" else "outbound",
#                     "partner_type": "customer" if rec.partner_type == "customer" else "supplier",
#                     "payment_method_line_id": rec.payment_method_line_id.id if rec.payment_method_line_id else False,
#                 }
#                 payment = self.env["account.payment"].create(pay_vals)
#                 payment.action_post()
#                 #
#                 # if ln.move_line_id and not ln.move_line_id.reconciled:
#                 #     lines_to_reconcile = ln.move_line_id + payment.move_id.line_ids.filtered(
#                 #         lambda l: l.account_id == ln.move_line_id.account_id and not l.reconciled
#                 #     )
#                 #     lines_to_reconcile.reconcile()
#
#                 ln.payment_id = payment.id
#
#             if rec.name == "/":
#                 rec.name = rec.env["ir.sequence"].next_by_code("batch.payment") or f"BATCH/{rec.id}"
#             rec.state = "validated"
#
#     # ----------------------------------------------------------------
#     # EXPORT (unchanged except: prefer payment fields when available)
#     # ----------------------------------------------------------------
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
#                 partner = ln.partner_id
#                 partner_code = (getattr(partner, "x_pastel_code", "") or "").strip() or \
#                                (partner.ref or partner.name or "").strip()
#
#                 # Try to carry a doc number if linked to a move (optional)
#                 doc_no = ""
#                 if ln.move_id:
#                      doc_no = ln.move_id.x_pastel_doc_no or ln.move_id.payment_reference or ln.move_id.name or ""
#                     # partner_code = (ln.partner_id.x_pastel_code or "").strip() or (
#                     #             ln.partner_id.ref or ln.partner_id.name or "").strip()
#                     # doc_no = str(rec.id)
#                 lines.append({
#                     "partner_code": partner_code,
#                     "invoice_doc_no": doc_no or None,
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
#
#             # Server log (exactly what we’re exporting)
#             _logger.info("Exporting BatchPayment %s to Sage with payload:\n%s", rec.name,
#                          json.dumps(payload, indent=2, ensure_ascii=False))
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
#     #-------------------------------------------
#     # action payment
#     # -------------------------------------------
#
#     def action_pay_batch(self):
#         """
#         Reconcile batch payments to invoices.
#         Result: invoice.payment_state becomes 'paid' when residual is 0.
#         """
#         for rec in self:
#             if rec.state not in ("validated", "exported"):
#                 raise UserError(_("Only Validated/Exported batches can be paid."))
#
#             if not rec.line_ids:
#                 raise UserError(_("No lines to pay."))
#
#             for ln in rec.line_ids:
#                 payment = ln.payment_id
#                 if not payment:
#                     # If your batch allows empty lines, just skip them
#                     continue
#
#                 if payment.state != "posted":
#                     raise UserError(_("Payment %s must be posted before paying the batch.") % payment.display_name)
#
#                 # 1) Determine invoice from the batch line (move_id preferred)
#                 invoice = ln.move_id or (ln.move_line_id.move_id if ln.move_line_id else False)
#
#                 # 2) Auto-link invoice from payment.batch_invoice_id (backfill move_id)
#                 if not invoice and getattr(payment, "batch_invoice_id", False):
#                     invoice = payment.batch_invoice_id
#                     ln.move_id = invoice.id  # store for future runs
#
#                 # 3) Still no invoice = cannot reconcile
#                 if not invoice:
#                     raise UserError(_(
#                         "Line with payment %s has no invoice/open item linked. "
#                         "This payment was not created from an invoice in Batch mode, "
#                         "or batch_invoice_id is empty."
#                     ) % payment.display_name)
#
#                 # Only posted invoices/bills can be reconciled
#                 if invoice.state != "posted":
#                     continue
#
#                 # 4) Invoice open AR/AP lines
#                 inv_lines = invoice.line_ids.filtered(lambda l:
#                                                       l.account_id.account_type in (
#                                                       "asset_receivable", "liability_payable")
#                                                       and not l.reconciled
#                                                       )
#                 if not inv_lines:
#                     # Already paid / nothing left to reconcile
#                     continue
#
#                 # 5) Payment open AR/AP lines
#                 pay_move = payment.move_id
#                 if not pay_move:
#                     raise UserError(_("Payment %s has no journal entry (move_id).") % payment.display_name)
#
#                 pay_lines = pay_move.line_ids.filtered(lambda l:
#                                                        l.account_id.account_type in (
#                                                        "asset_receivable", "liability_payable")
#                                                        and not l.reconciled
#                                                        )
#                 if not pay_lines:
#                     continue
#
#                 # 6) Reconcile per account (important if multiple AR/AP accounts exist)
#                 for acc in inv_lines.mapped("account_id"):
#                     inv_acc_lines = inv_lines.filtered(lambda l: l.account_id == acc and not l.reconciled)
#                     pay_acc_lines = pay_lines.filtered(lambda l: l.account_id == acc and not l.reconciled)
#                     if inv_acc_lines and pay_acc_lines:
#                         (inv_acc_lines + pay_acc_lines).reconcile()
#
#                 # Odoo will automatically update invoice.payment_state based on residual
#
#             # 7) Mark batch as paid (only if you added that state)
#             if "state" in rec._fields:
#                 sel = dict(rec._fields["state"].selection or [])
#                 if "paid" in sel:
#                     rec.state = "paid"
#
#     #
#     # def action_pay_batch(self):
#     #         """
#     #         Reconcile batch payments to invoices.
#     #         Result: invoice payment_state becomes 'paid' when residual is 0.
#     #         """
#     #         for rec in self:
#     #             if rec.state not in ("validated", "exported"):
#     #                 raise UserError(_("Only Validated/Exported batches can be paid."))
#     #
#     #             if not rec.line_ids:
#     #                 raise UserError(_("No lines to pay."))
#     #
#     #             for ln in rec.line_ids:
#     #                 payment = ln.payment_id
#     #                 if not payment:
#     #                     # If you allow lines without payment_id, skip or raise
#     #                     continue
#     #                 if payment.state != "posted":
#     #                     raise UserError(_("Payment %s must be posted before paying the batch.") % payment.display_name)
#     #
#     #                 # 1) Determine invoice move from the line (prefer move_id, otherwise derive from move_line_id)
#     #                 invoice = ln.move_id
#     #                 if not invoice and ln.move_line_id:
#     #                     invoice = ln.move_line_id.move_id
#     #
#     #                 # if not invoice:
#     #                 #     # This line was created by selecting posted payments only (no invoice link)
#     #                 #     # You cannot pay any invoice unless we know which invoice to reconcile against.
#     #                 #     raise UserError(_(
#     #                 #         "Line with payment %s has no invoice/open item linked. "
#     #                 #         "Set move_id or move_line_id on the batch line so Pay Batch can reconcile."
#     #                 #     ) % payment.display_name)
#     #
#     #                 # Try auto-linking from payment.batch_invoice_id
#     #                 if not invoice and payment and getattr(payment, "batch_invoice_id", False):
#     #                     invoice = payment.batch_invoice_id
#     #                     # store it on the batch line so next time it is linked
#     #                     ln.move_id = invoice.id
#     #
#     #                 if not invoice:
#     #                     raise UserError(_(
#     #                         "Line with payment %s has no invoice/open item linked. "
#     #                         "This payment was not created from an invoice in Batch mode, "
#     #                         "or batch_invoice_id is empty."
#     #                     ) % payment.display_name)
#     #
#     #                 if invoice.state != "posted":
#     #                     continue  # only posted invoices/bills can be reconciled
#     #
#     #                 # 2) Get open receivable/payable lines on the invoice
#     #                 inv_lines = invoice.line_ids.filtered(lambda l:
#     #                                                       l.account_id.account_type in (
#     #                                                       "asset_receivable", "liability_payable")
#     #                                                       and not l.reconciled
#     #                                                       )
#     #                 if not inv_lines:
#     #                     # already paid or nothing to reconcile
#     #                     continue
#     #
#     #                 # 3) Get matching receivable/payable lines from the payment journal entry
#     #                 pay_move = payment.move_id
#     #                 if not pay_move:
#     #                     raise UserError(_("Payment %s has no journal entry (move_id).") % payment.display_name)
#     #
#     #                 pay_lines = pay_move.line_ids.filtered(lambda l:
#     #                                                        l.account_id.account_type in (
#     #                                                        "asset_receivable", "liability_payable")
#     #                                                        and not l.reconciled
#     #                                                        )
#     #                 if not pay_lines:
#     #                     continue
#     #
#     #                 # 4) Reconcile per account (important when multiple AR/AP accounts exist)
#     #                 for acc in (inv_lines.mapped("account_id")):
#     #                     inv_acc_lines = inv_lines.filtered(lambda l: l.account_id == acc and not l.reconciled)
#     #                     pay_acc_lines = pay_lines.filtered(lambda l: l.account_id == acc and not l.reconciled)
#     #                     if inv_acc_lines and pay_acc_lines:
#     #                         (inv_acc_lines + pay_acc_lines).reconcile()
#     #
#     #                 # After reconciliation, Odoo updates invoice.payment_state automatically
#     #                 # invoice.payment_state will become 'paid' if residual is 0.
#     #
#     #             # Optional: mark batch as paid when done
#     #             if "paid" in (dict(self._fields["state"].selection) if "state" in self._fields else {}):
#     #                 rec.state = "paid"
#
#     # def action_pay_batch(self):
#     #     for rec in self:
#     #         if rec.state not in ("validated", "exported"):
#     #             raise UserError(_("Only validated/exported batches can be paid."))
#     #
#     #         for ln in rec.line_ids:
#     #             pay = ln.payment_id
#     #             if not pay or pay.state != "posted":
#     #                 continue
#     #
#     #             # If this line came from an open item, we can reconcile it now
#     #             if ln.move_line_id and not ln.move_line_id.reconciled and pay.move_id:
#     #                 pay_lines = pay.move_id.line_ids.filtered(
#     #                     lambda l: l.account_id == ln.move_line_id.account_id and not l.reconciled
#     #                 )
#     #                 (ln.move_line_id + pay_lines).reconcile()
#     #
#     #         rec.state = "paid"
#
#     @api.onchange("journal_id", "payment_method_line_id", "partner_id", "company_id")
#     def _onchange_filters_prune_lines(self):
#         for rec in self:
#             if not rec.line_ids:
#                 continue
#             to_keep = rec.line_ids.filtered(lambda ln:
#                                             ln.payment_id
#                                             and ln.payment_id.state == "posted"
#                                             and (not rec.journal_id or ln.payment_id.journal_id == rec.journal_id)
#                                             and (not rec.company_id or ln.payment_id.company_id == rec.company_id)
#                                             and (
#                                                         not rec.payment_method_line_id or ln.payment_id.payment_method_line_id == rec.payment_method_line_id)
#                                             and (
#                                                         rec.partner_type != "customer" or not rec.partner_id or ln.payment_id.partner_id == rec.partner_id)
#                                             )
#             if len(to_keep) != len(rec.line_ids):
#                 rec.line_ids = [(6, 0, to_keep.ids)]
#
# # -------------------------------------------------------------------
# # Lines: now centered on account.payment with related columns
# # -------------------------------------------------------------------
#
# class BatchPaymentLine(models.Model):
#     _name = "batch.payment.line"
#     _description = "Batch Payment Line"
#     _order = "id asc"
#
#     batch_id = fields.Many2one("batch.payment", required=True, ondelete="cascade")
#     payment_id = fields.Many2one("account.payment", string="Payment")
#
#     # Display columns (related)
#     number = fields.Char(related="payment_id.name", store=True)
#     date = fields.Date(related="payment_id.date", store=True)
#     journal_id = fields.Many2one("account.journal", related="payment_id.journal_id", store=True)
#     company_id = fields.Many2one("res.company", related="payment_id.company_id", store=True)
#     payment_method_line_id = fields.Many2one("account.payment.method.line", related="payment_id.payment_method_line_id", store=True)
#     partner_id = fields.Many2one("res.partner", related="payment_id.partner_id", store=True, string="Customer/Supplier")
#     status = fields.Selection(related="payment_id.state", store=True, string="Status")
#
#     amount = fields.Monetary(currency_field="currency_id",
#                              compute="_compute_amount_from_payment", store=True)
#     currency_id = fields.Many2one(related="batch_id.currency_id", store=True)
#
#     # legacy fields (kept)
#     move_id = fields.Many2one("account.move", string="Invoice/Bill")
#     move_line_id = fields.Many2one("account.move.line", string="Open Item")
#     communication = fields.Char()
#     # selected = fields.Boolean(string="Select")
#
#     @api.depends("payment_id.amount", "payment_id.currency_id")
#     def _compute_amount_from_payment(self):
#         for ln in self:
#             ln.amount = abs(ln.payment_id.amount) if ln.payment_id else (ln.amount or 0.0)
#
#     # ... your model definitions ...
#
#     def _check_payment_matches_header(self):
#         """
#         Called on create/write of batch.payment.line to enforce that chosen payment
#         matches the batch header filters (journal, company, method, state).
#         Make sure EVERY formatted string uses % with a dict (mapping).
#         """
#         for line in self:
#             pay = line.payment_id
#             batch = line.batch_id
#             if not pay or not batch:
#                 continue
#
#             # journal must match
#             if batch.journal_id and pay.journal_id != batch.journal_id:
#                 msg = _("Payment %(p)s journal (%(pj)s) doesn't match batch journal (%(bj)s).") % {
#                     "p": pay.display_name,
#                     "pj": pay.journal_id.display_name or pay.journal_id.name,
#                     "bj": batch.journal_id.display_name or batch.journal_id.name,
#                 }
#                 raise ValidationError(msg)
#
#             # company must match
#             if batch.company_id and pay.company_id != batch.company_id:
#                 msg = _("Payment %(p)s company (%(pc)s) doesn't match batch company (%(bc)s).") % {
#                     "p": pay.display_name,
#                     "pc": pay.company_id.display_name or pay.company_id.name,
#                     "bc": batch.company_id.display_name or batch.company_id.name,
#                 }
#                 raise ValidationError(msg)
#
#             # posted only
#             if pay.state != "posted":
#                 msg = _("Payment %(p)s is not posted (state: %(st)s).") % {
#                     "p": pay.display_name,
#                     "st": pay.state,
#                 }
#                 raise ValidationError(msg)
#
#             # optional: payment method line must match when batch has one fixed (if you store it)
#             if hasattr(batch, "payment_method_line_id") and batch.payment_method_line_id:
#                 if pay.payment_method_line_id != batch.payment_method_line_id:
#                     msg = _("Payment %(p)s method (%(pm)s) doesn't match batch method (%(bm)s).") % {
#                         "p": pay.display_name,
#                         "pm": pay.payment_method_line_id.display_name or pay.payment_method_line_id.name,
#                         "bm": batch.payment_method_line_id.display_name or batch.payment_method_line_id.name,
#                     }
#                     raise ValidationError(msg)
#
#
#
#
