"""Batch payment header/lines, Sage export, validation, and settings."""

# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_is_zero
import logging
import json

_logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Batch Payment
# -------------------------------------------------------------------
class BatchPayment(models.Model):
    """Group payments/invoices for validation, Sage export, and reconciliation."""

    _name = "batch.payment"
    _description = "Batch Payment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default="/", readonly=True)

    # state = fields.Selection([
    #     ("draft", "Draft"),
    #     ("validated", "Validated"),
    #     ("exported", "Exported"),
    #     ("paid", "Paid"),
    # ], default="draft", tracking=True)

    state = fields.Selection([
        ("draft", "Draft"),
        ("validated", "Validated"),
        ("exported", "Exported"),
        ("partial", "Partial Paid"),
        ("paid", "Paid"),
        ('cancelled', 'Cancelled'),
    ], default="draft", tracking=True)

    invoice_ids = fields.Many2many(
        "account.move",
        "batch_payment_invoice_rel",
        "batch_id",
        "invoice_id",
        string="Invoices in Batch",
        domain="[('move_type','in',('out_invoice','in_invoice'))]",
        help="Invoices explicitly paid in this batch."
    )

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
    company_id = fields.Many2one("res.company", required=False, default=lambda s: s.env.company, index=True,)

    line_ids = fields.One2many("batch.payment.line", "batch_id", string="Lines")

    amount_total = fields.Monetary(currency_field="currency_id", compute="_compute_amounts", store=True)
    exported_ref = fields.Char("Export Reference", readonly=True)
    note = fields.Text()

    export_history_ids = fields.One2many(
        "batch.payment.export.history",
        "batch_id",
        string="Export History",
    )

    #============================================================
    #BATCH WIZARD
    #============================================================
    amount_due = fields.Monetary(
        string="Amount Due",
        currency_field="currency_id",
        compute="_compute_amount_due",
        store=True,
    )

    amount_received = fields.Monetary(
        string="Amount Received",
        currency_field="currency_id",
        copy=False,
    )

    payment_difference = fields.Monetary(
        string="Difference",
        currency_field="currency_id",
        copy=False,
    )

    line_count = fields.Integer(
        string="Lines",
        compute="_compute_gui_helpers",
    )
    sage_exported = fields.Boolean(
        string="Exported to Sage",
        compute="_compute_gui_helpers",
    )
    next_step_hint = fields.Char(
        string="Next step",
        compute="_compute_gui_helpers",
    )

    @api.depends(
        "line_ids",
        "exported_ref",
        "state",
        "amount_due",
        "amount_received",
    )
    def _compute_gui_helpers(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.sage_exported = bool(rec.exported_ref)
            if rec.state == "draft":
                rec.next_step_hint = _(
                    "Add payment lines, then click Validate."
                )
            elif rec.state == "validated":
                rec.next_step_hint = _(
                    "Export to Sage and/or Receive Payment in Odoo — either order is fine."
                )
            elif rec.state == "exported":
                rec.next_step_hint = _(
                    "Exported to Sage. Use Set to Draft if you need to change or re-export this batch."
                )
            elif rec.state == "partial":
                rec.next_step_hint = _(
                    "Partial payment received. Receive the balance, or Export to Sage if needed."
                )
            elif rec.state == "paid":
                rec.next_step_hint = _(
                    "Fully paid in Odoo. Export to Sage if not done yet."
                )
            elif rec.state == "cancelled":
                rec.next_step_hint = _("This batch was cancelled.")
            else:
                rec.next_step_hint = False

    @api.depends("line_ids.amount")
    def _compute_amount_due(self):
        """Sum line amounts into the batch amount due."""
        for rec in self:
            rec.amount_due = sum(rec.line_ids.mapped("amount"))

    def action_open_receive_payment(self):

        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Receive Payment",
            "res_model": "batch.payment.receive.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_batch_id": self.id,
            }
        }

    credit_balance_before = fields.Monetary(
        string="Credit Before",
        currency_field="currency_id",
        readonly=True,
    )

    credit_applied = fields.Monetary(
        string="Credit Applied",
        currency_field="currency_id",
        readonly=True,
    )

    credit_balance_after = fields.Monetary(
        string="Credit After",
        currency_field="currency_id",
        readonly=True,
    )

    amount_due_after_credit = fields.Monetary(
        string="Amount Due After Credit",
        currency_field="currency_id",
        readonly=True,
    )

    #============================================END================================

    @api.depends("line_ids.amount")
    def _compute_amounts(self):
        """Compute total batch amount from line amounts."""
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped("amount"))

    # ----------------------------------------------------------------
    # Load open items (unpaid AR/AP move lines)
    # ----------------------------------------------------------------
    def action_load_open_items(self):
        """Add unpaid receivable/payable move lines to the batch."""
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only draft batches can load lines"))

        # dom = [
        #     ("move_id.state", "=", "posted"),
        #     ("reconciled", "=", False),
        #     ("company_id", "=", self.company_id.id),
        # ]

        dom = [
            ("move_id.state", "=", "posted"),
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

        # for aml in items:
        #     residual = aml.amount_residual if aml.currency_id != aml.company_currency_id else aml.amount_residual
        #     amount = abs(residual)
        #     if amount <= 0:
        #         continue
        #     new_lines.append((0, 0, {
        #         "move_id": aml.move_id.id,
        #         "move_line_id": aml.id,
        #         "communication": aml.move_id.name or aml.ref or "",
        #         "amount": amount,
        #     }))
        # for aml in items:
        #
        #     invoice = aml.move_id
        #
        #     # -----------------------------------------
        #     # PARTIAL BATCH INVOICE
        #     # -----------------------------------------
        #     if (
        #             invoice.batch_payment_state == "partial"
        #             and invoice.amount_outstanding_batch > 0
        #     ):
        #
        #         amount = invoice.amount_outstanding_batch
        #
        #     else:
        #
        #         residual = aml.amount_residual
        #         amount = abs(residual)
        #
        #     if amount <= 0:
        #         continue
        #
        #     new_lines.append((0, 0, {
        #         "move_id": invoice.id,
        #         "move_line_id": aml.id,
        #         "communication": invoice.name or aml.ref or "",
        #         "amount": amount,
        #     }))

        for aml in items:

            invoice = aml.move_id

            if invoice.batch_payment_state == "paid":
                continue

            if (
                    invoice.batch_payment_state == "partial"
                    and invoice.amount_outstanding_batch > 0
            ):

                amount = invoice.amount_outstanding_batch

            else:

                amount = abs(aml.amount_residual)

            if amount <= 0:
                continue

            new_lines.append((0, 0, {
                "move_id": invoice.id,
                "move_line_id": aml.id,
                "communication": invoice.name or aml.ref or "",
                "amount": amount,
            }))

        if new_lines:
            self.write({"line_ids": new_lines})

    # ----------------------------------------------------------------
    # Load posted payments (and auto-link invoice using payment.batch_invoice_id)
    # ----------------------------------------------------------------
    def action_load_posted_payments(self):
        """Add posted payments matching batch filters."""
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
        """Create/post payments, apply credit, and mark batch validated."""
        for rec in self:

            if rec.state != "draft":
                raise UserError(_("Only draft batches can be validated."))

            if not rec.line_ids:
                raise UserError(_("No lines."))

            # ==========================================
            # APPLY CUSTOMER CREDIT
            # ==========================================

            first_invoice = rec.line_ids[:1].move_id

            if first_invoice:

                partner = first_invoice.partner_id

                credits = self.env["customer.credit"].search([
                    ("partner_id", "=", partner.id),
                    ("state", "=", "open")
                ], order="create_date asc")

                available_credit = sum(
                    credits.mapped("balance")
                )

                rec.credit_balance_before = available_credit

                remaining_due = rec.amount_due
                applied_credit = 0.0

                for credit in credits:

                    if remaining_due <= 0:
                        break

                    apply_amount = min(
                        credit.balance,
                        remaining_due
                    )

                    self.env["customer.credit.usage"].create({
                        "credit_id": credit.id,
                        "source_batch_id": credit.batch_id.id,
                        "applied_batch_id": rec.id,
                        "amount": apply_amount,
                        "currency_id": rec.currency_id.id,
                    })

                    credit.balance -= apply_amount

                    if float_is_zero(
                            credit.balance,
                            precision_rounding=rec.currency_id.rounding
                    ):
                        credit.state = "used"

                    remaining_due -= apply_amount
                    applied_credit += apply_amount

                rec.credit_applied = applied_credit

                rec.credit_balance_after = sum(
                    credits.mapped("balance")
                )

                rec.amount_due_after_credit = remaining_due

                _logger.warning(
                    "FIRST INVOICE: %s",
                    first_invoice
                )

                _logger.warning(
                    "PARTNER: %s",
                    partner.display_name if partner else "NONE"
                )

                _logger.warning(
                    "CREDITS FOUND: %s",
                    len(credits)
                )

            # ==========================================
            # EXISTING VALIDATION LOGIC
            # =========================================

            for ln in rec.line_ids:
                # A) already linked to a posted payment
                if ln.payment_id:
                    if ln.payment_id.state != "posted":
                        raise UserError(_("Payment %s is not posted.") % ln.payment_id.display_name)

                    if not ln.move_id and getattr(ln.payment_id, "batch_invoice_id", False):
                        ln.move_id = ln.payment_id.batch_invoice_id.id
                    continue

                invoice = ln.move_id or (
                    ln.move_line_id.move_id
                    if ln.move_line_id else False
                )

                if not invoice:
                    raise UserError(
                        _("Line has no invoice.")
                    )

                # ==================================================
                # OUTSTANDING BALANCE INVOICE
                # ==================================================

                if (
                        invoice.batch_payment_state == "partial"
                        and invoice.amount_outstanding_batch > 0
                ):


                    payment_vals = {
                        "payment_type": "inbound",
                        "partner_type": "customer",
                        "partner_id": invoice.partner_id.id,
                        "amount": ln.amount,
                        "date": rec.payment_date,
                        "journal_id": rec.journal_id.id,
                        "company_id": invoice.company_id.id,
                        "currency_id": invoice.currency_id.id,
                        "ref": invoice.name,
                        "batch_invoice_id": invoice.id,
                    }

                    payment = self.env[
                        "account.payment"
                    ].create(payment_vals)

                    payment.action_post()

                    ln.payment_id = payment.id
                    ln.move_id = invoice.id

                    # -------------------------------------------------
                    # Refresh Batch Status After Recovery Payment
                    # -------------------------------------------------

                    invoice.invalidate_recordset()

                    if invoice.amount_residual <= 0:

                        invoice.write({
                            "batch_payment_state": "paid",
                            "amount_paid_batch": invoice.amount_total,
                            "amount_outstanding_batch": 0.0,
                        })

                    else:

                        invoice.write({
                            "batch_payment_state": "partial",
                            "amount_paid_batch": (
                                    invoice.amount_total
                                    - invoice.amount_residual
                            ),
                            "amount_outstanding_batch": (
                                invoice.amount_residual
                            ),
                        })

                    _logger.warning(
                        "OUTSTANDING PAYMENT CREATED %s -> %s",
                        invoice.name,
                        payment.name
                    )

                    continue

                # ==================================================
                # NORMAL INVOICE
                # ==================================================

                if invoice.state != "posted":
                    raise UserError(
                        _("Invoice %s must be posted.")
                        % invoice.display_name
                    )

                ctx = dict(self.env.context or {})
                ctx.update({
                    "active_model": "account.move",
                    "active_ids": [invoice.id],
                    "active_id": invoice.id,
                    "batch_skip_reconcile": True,
                })

                wizard_vals = {
                    "amount": ln.amount or invoice.amount_residual,
                    "payment_date": rec.payment_date,
                    "journal_id": rec.journal_id.id,
                }

                if rec.payment_method_line_id:
                    wizard_vals["payment_method_line_id"] = (
                        rec.payment_method_line_id.id
                    )

                pay_wizard = self.env[
                    "account.payment.register"
                ].with_context(ctx).create(
                    wizard_vals
                )

                action_res = pay_wizard.action_create_payments()

                payments = pay_wizard.payment_id

                if not payments and isinstance(action_res, dict):
                    if (
                            action_res.get("res_model")
                            == "account.payment"
                            and action_res.get("res_id")
                    ):
                        payments = self.env[
                            "account.payment"
                        ].browse(
                            action_res["res_id"]
                        ).exists()

                if not payments:
                    raise UserError(
                        _("No payment was created for invoice %s.")
                        % invoice.display_name
                    )

                payment = payments[0]

                if payment.state != "posted":
                    raise UserError(
                        _("Created payment %s is not posted.")
                        % payment.display_name
                    )

                if not payment.batch_invoice_id:
                    payment.batch_invoice_id = invoice.id

                ln.payment_id = payment.id
                ln.move_id = invoice.id

                payment.batch_payment_state = "validated"

                invoice.write({
                    "batch_payment_state": "validated",
                    "amount_paid_batch": 0.0,
                    "amount_outstanding_batch": invoice.amount_total,
                })

            # if rec.name == "/":
            #     rec.name = rec.env["ir.sequence"].next_by_code("batch.payment") or f"BATCH/{rec.id}"
            # rec.state = "validated"
            #
            # rec.line_ids.mapped('payment_id').write({
            #     'batch_payment_state': 'validated'
            # })

            if rec.name == "/":
                rec.name = (
                        rec.env["ir.sequence"]
                        .next_by_code("batch.payment")
                        or f"BATCH/{rec.id}"
                )

            rec.state = "validated"

    # ----------------------------------------------------------------
    # Export to Sage
    # ----------------------------------------------------------------
    def action_export_sage(self):
        """Export via sage.job (visible in Sage Connector → Jobs), then update batch state.

        Payment in Odoo and Sage export are independent: a batch can be paid
        first then exported, or exported first then paid.
        """
        Job = self.env["sage.job"].sudo()
        for rec in self:
            if rec.state not in ("validated", "exported", "partial", "paid"):
                raise UserError(_(
                    "Only validated, exported, partial, or paid batches can be exported to Sage."
                ))
            if rec.exported_ref:
                raise UserError(_(
                    "This batch was already exported to Sage (ref: %s)."
                ) % rec.exported_ref)

            history_payload = {
                "via": "sage.job",
                "batch": rec.name,
                "batch_id": rec.id,
            }
            try:
                backend = self.env["sage.backend"]._for_company(
                    rec.company_id or self.env.company
                )
                job = Job.enqueue(
                    backend,
                    "export_receipt_batch",
                    payload={"batch": rec.name, "batch_id": rec.id},
                    res_model="batch.payment",
                    res_id=rec.id,
                    idempotency_key="odoo-batch-export-%s-%s" % (
                        rec.id, fields.Datetime.now(),
                    ),
                )
                job.action_process_now()
                result = {}
                if job.result:
                    try:
                        result = json.loads(job.result)
                    except Exception:
                        result = {"raw": job.result}
                sage_ref = (result or {}).get("batch_id") or rec.exported_ref or rec.name
                self.env["batch.payment.export.history"].create({
                    "batch_id": rec.id,
                    "state": "success",
                    "sage_reference": sage_ref,
                    "request_payload": json.dumps(history_payload, indent=2),
                    "response_payload": json.dumps(result, indent=2, default=str),
                })
                rec.exported_ref = sage_ref

                for line in rec.line_ids:
                    invoice = line.move_id
                    payment = line.payment_id
                    if not invoice:
                        continue
                    # Do not downgrade invoices already marked paid/partial in Odoo.
                    if invoice.batch_payment_state not in ("paid", "partial"):
                        invoice.write({
                            "batch_payment_state": "exported",
                            "batch_payment_id": rec.id,
                        })
                    if not payment:
                        continue
                    if invoice.state != "posted" or payment.state != "posted":
                        continue
                    inv_lines = invoice.line_ids.filtered(
                        lambda l: l.account_id.account_type in (
                            "asset_receivable", "liability_payable"
                        ) and not l.reconciled
                    )
                    pay_lines = payment.move_id.line_ids.filtered(
                        lambda l: l.account_id in inv_lines.mapped("account_id") and not l.reconciled
                    )
                    if inv_lines and pay_lines:
                        (inv_lines + pay_lines).reconcile()

                # Preserve Odoo payment progress (partial/paid); only move validated → exported.
                if rec.state == "validated":
                    rec.state = "exported"
                    rec.line_ids.mapped("payment_id").filtered(
                        lambda p: p.batch_payment_state not in ("paid", "partial")
                    ).write({"batch_payment_state": "exported"})
            except Exception as e:
                self.env["batch.payment.export.history"].create({
                    "batch_id": rec.id,
                    "state": "failed",
                    "request_payload": json.dumps(history_payload, indent=2),
                    "response_payload": str(e),
                })
                raise UserError(_("Sage export failed: %s") % e)

    def action_pay_batch(self):
        """Reconcile payments and mark batch and invoices paid."""
        for batch in self:
            if batch.state not in ("validated", "exported"):
                raise UserError(_("Only validated or exported batches can be paid."))

            for line in batch.line_ids:
                invoice = line.move_id
                payment = line.payment_id

                if not invoice or not payment:
                    continue

                if invoice.state != "posted" or payment.state != "posted":
                    continue

                # Find receivable/payable lines
                inv_lines = invoice.line_ids.filtered(
                    lambda l: l.account_id.account_type in (
                    'asset_receivable', 'liability_payable') and not l.reconciled
                )
                pay_lines = payment.move_id.line_ids.filtered(
                    lambda l: l.account_id == inv_lines.account_id and not l.reconciled
                )

                # Reconcile
                (inv_lines + pay_lines).reconcile()

                # Mark batch info
                invoice.write({
                    "batch_payment_state": "paid",
                    "batch_payment_id": batch.id,
                })

            batch.state = "paid"

            batch.line_ids.mapped('payment_id').write({
                'batch_payment_state': 'paid'
            })

        return {"type": "ir.actions.client", "tag": "reload"}


    @api.onchange("journal_id", "payment_method_line_id", "partner_id", "company_id")
    def _onchange_filters_prune_lines(self):
        """Remove batch lines that no longer match header filters."""
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

    # def action_cancel(self):
    #
    #     for rec in self:
    #
    #         if rec.state == "paid":
    #             raise UserError(
    #                 _("You cannot cancel a paid batch.")
    #             )
    #
    #         usages = self.env["customer.credit.usage"].search([
    #             ("applied_batch_id", "=", rec.id)
    #         ])
    #
    #         for usage in usages:
    #
    #             credit = usage.credit_id
    #
    #             credit.balance += usage.amount
    #
    #             if credit.balance > 0:
    #                 credit.state = "open"
    #
    #         usages.unlink()
    #
    #         for line in rec.line_ids:
    #
    #             if line.move_id:
    #                 line.move_id.write({
    #                     "batch_payment_state": "not_paid",
    #                     "amount_paid_batch": 0.0,
    #                     "amount_outstanding_batch": line.amount,
    #                 })
    #
    #         rec.line_ids.mapped("payment_id").write({
    #             "batch_payment_state": "not_paid"
    #         })
    #
    #
    #
    #         rec.credit_applied = 0.0
    #         rec.credit_balance_after = rec.credit_balance_before
    #         rec.amount_due_after_credit = rec.amount_due
    #
    #         rec.message_post(
    #             body=_(
    #                 "Credit allocations restored because batch was cancelled."
    #             )
    #         )
    #
    #         rec.state = "cancelled"
    #
    #     return True

    def action_cancel(self):

        for rec in self:

            if rec.state in ("paid", "exported"):
                raise UserError(
                    _("You cannot cancel an exported or paid batch.")
                )

            usages = self.env["customer.credit.usage"].search([
                ("applied_batch_id", "=", rec.id)
            ])

            for usage in usages:

                credit = usage.credit_id

                credit.balance += usage.amount

                if credit.balance > 0:
                    credit.state = "open"

            usages.unlink()

            for line in rec.line_ids:

                if line.move_id:
                    line.move_id.write({
                        "batch_payment_state": "not_paid",
                        "amount_paid_batch": 0.0,
                        "amount_outstanding_batch": line.amount,
                    })

            rec.line_ids.mapped("payment_id").write({
                "batch_payment_state": "not_paid"
            })

            rec.credit_applied = 0.0
            rec.credit_balance_after = rec.credit_balance_before
            rec.amount_due_after_credit = rec.amount_due

            rec.message_post(
                body=_(
                    "Credit allocations restored because batch was cancelled."
                )
            )

            rec.state = "cancelled"

        return True

    def action_set_to_draft(self):
        """Reset validated/exported/cancelled batches back to draft for editing."""
        for rec in self:
            if rec.state not in ("validated", "exported", "cancelled"):
                raise UserError(_(
                    "Only validated, exported, or cancelled batches can be reset to draft."
                ))
            if rec.state == "paid":
                raise UserError(_("Paid batches cannot be reset to draft."))

            usages = self.env["customer.credit.usage"].search([
                ("applied_batch_id", "=", rec.id),
            ])
            for usage in usages:
                credit = usage.credit_id
                credit.balance += usage.amount
                if credit.balance > 0:
                    credit.state = "open"
            usages.unlink()

            for line in rec.line_ids:
                if line.move_id:
                    line.move_id.write({
                        "batch_payment_state": "not_paid",
                        "amount_paid_batch": 0.0,
                        "amount_outstanding_batch": line.amount,
                        "batch_payment_id": False,
                    })
            rec.line_ids.mapped("payment_id").write({
                "batch_payment_state": "not_paid",
            })

            rec.write({
                "state": "draft",
                "exported_ref": False,
                "amount_received": 0.0,
                "payment_difference": 0.0,
                "credit_applied": 0.0,
                "credit_balance_after": rec.credit_balance_before,
                "amount_due_after_credit": rec.amount_due,
            })
            rec.message_post(body=_("Batch reset to draft."))
        return True

    # def action_load_outstanding_invoices(self):
    #
    #     self.ensure_one()
    #
    #     # invoices = self.env["account.move"].search([
    #     #     ("move_type", "=", "out_invoice"),
    #     #     ("state", "=", "posted"),
    #     #     ("batch_payment_state", "=", "partial"),
    #     #     ("amount_outstanding_batch", ">", 0),
    #     # ])
    #
    #     invoices = self.env["account.move"].search([
    #         ("move_type", "=", "out_invoice"),
    #         ("state", "=", "posted"),
    #         ("company_id", "=", self.company_id.id),
    #         ("amount_outstanding_batch", ">", 0),
    #         ("has_batch_payment", "=", True),
    #     ])
    #     invoices = invoices.filtered(
    #         lambda inv: self.env["account.payment"].search_count([
    #             ("batch_invoice_id", "=", inv.id)
    #         ]) > 0
    #     )
    #
    #     existing_invoice_ids = self.line_ids.mapped("move_id").ids
    #
    #     for invoice in invoices:
    #
    #         if invoice.id in existing_invoice_ids:
    #             continue
    #
    #         self.line_ids = [(0, 0, {
    #             "move_id": invoice.id,
    #             "communication": (
    #                 f"{invoice.name} "
    #                 f"(Outstanding Balance)"
    #             ),
    #             "amount": invoice.amount_outstanding_batch,
    #         })]
    #
    #     return True

    def action_load_outstanding_invoices(self):

        self.ensure_one()

        partial_batches = self.env["batch.payment"].search([
            ("state", "=", "partial"),
            ("company_id", "=", self.company_id.id),
        ])

        invoices = partial_batches.mapped(
            "line_ids.payment_id.batch_invoice_id"
        ).filtered(
            lambda inv:
            inv
            and inv.amount_outstanding_batch > 0
        )

        existing_invoice_ids = self.line_ids.mapped("move_id").ids

        new_lines = []

        # if invoices:
        #     new_lines.append((0, 0, {
        #         "display_type": "line_section",
        #         "communication": "Outstanding Invoices From Partial Batches",
        #     }))

        for invoice in invoices:

            if invoice.id in existing_invoice_ids:
                continue

            payment = self.env["account.payment"].search([
                ("batch_invoice_id", "=", invoice.id),
            ], order="create_date desc,id desc", limit=1)

            status = dict(
                invoice._fields["batch_payment_state"].selection
            ).get(invoice.batch_payment_state)

            _logger.warning(
                "ADDING OUTSTANDING INVOICE %s | STATE=%s | OUTSTANDING=%s",
                invoice.name,
                invoice.batch_payment_state,
                invoice.amount_outstanding_batch,
            )

            # new_lines.append((0, 0, {
            #     "payment_id": payment.id if payment else False,
            #     "move_id": invoice.id,
            #     "communication": f"{invoice.name} ({status})",
            #     "amount": invoice.amount_outstanding_batch,
            # }))
            # new_lines.append((0, 0, {
            #     "payment_id": payment.id if payment else False,
            #     "move_id": invoice.id,
            #     "source_batch_id": invoice.batch_payment_id.id if hasattr(invoice, 'batch_payment_id') else False,
            #     "communication": f"{invoice.name} ({status})",
            #     # "amount": invoice.amount_outstanding_batch,
            #     "amount": invoice.amount_outstanding_batch,
            # }))

            new_lines.append((0, 0, {
                "payment_id": payment.id if payment else False,
                "move_id": invoice.id,
                "amount": invoice.amount_outstanding_batch,
                "communication": f"{invoice.name} ({status})",
            }))

        if new_lines:
            self.write({
                "line_ids": new_lines
            })

        return True

    def _recompute_batch_state(self):

        for batch in self:

            lines = batch.line_ids.filtered(
                lambda l: l.move_id
            )

            if not lines:
                continue

            unpaid = lines.filtered(
                lambda l:
                l.move_id.batch_payment_state != "paid"
            )

            if unpaid:
                batch.state = "partial"
            else:
                batch.state = "paid"

            _logger.warning(
                "BATCH %s RECALCULATED -> %s",
                batch.name,
                batch.state
            )

# Lines
# -------------------------------------------------------------------
class BatchPaymentLine(models.Model):
    """Single payment or open-item line belonging to a batch payment."""

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

    manual_amount = fields.Monetary(
        currency_field="currency_id"
    )

    # IMPORTANT
    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
        required=True,
        default=0.0,
    )

    partner_id = fields.Many2one("res.partner", related="payment_id.partner_id", store=True, string="Customer/Supplier")
    status = fields.Selection(related="payment_id.state", store=True, string="Status")

    # amount = fields.Monetary(currency_field="currency_id", compute="_compute_amount_from_payment", store=True)
    # amount = fields.Monetary(
    #     string="Amount",
    #     currency_field="currency_id",
    # )
    currency_id = fields.Many2one(related="batch_id.currency_id", store=True)

    move_id = fields.Many2one("account.move", string="Invoice/Bill")
    move_line_id = fields.Many2one("account.move.line", string="Open Item")
    communication = fields.Char()
    source_batch_id = fields.Many2one(
        "batch.payment",
        string="Source Batch",
        compute="_compute_source_batch",
    )

    # display_type = fields.Selection([
    #     ('line_section', 'Section'),
    #     ('line_note', 'Note'),
    # ], default=False)

    @api.depends("move_id")
    def _compute_source_batch(self):

        for line in self:

            line.source_batch_id = False

            if not line.move_id:
                continue

            source_line = self.env[
                "batch.payment.line"
            ].search([
                ("move_id", "=", line.move_id.id),
                ("batch_id.state", "=", "partial"),
            ], order="id asc", limit=1)

            line.source_batch_id = source_line.batch_id

    # def _compute_source_batch(self):
    #     for line in self:
    #         source_line = self.env["batch.payment.line"].search([
    #             ("move_id", "=", line.move_id.id),
    #             ("batch_id.state", "=", "partial"),
    #         ], order="id asc", limit=1)
    #
    #         line.source_batch_id = source_line.batch_id

    # @api.depends("payment_id.amount", "payment_id.currency_id")
    # def _compute_amount_from_payment(self):
    #     for ln in self:
    #         ln.amount = abs(ln.payment_id.amount) if ln.payment_id else (ln.amount or 0.0)

    # @api.depends(
    #     "payment_id.amount",
    #     "manual_amount"
    # )
    # def _compute_amount_from_payment(self):
    #
    #     for ln in self:
    #
    #         if ln.payment_id:
    #
    #             ln.amount = abs(
    #                 ln.payment_id.amount
    #             )
    #
    #         else:
    #
    #             ln.amount = (
    #                     ln.manual_amount or 0.0
    #             )

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

