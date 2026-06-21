from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = "account.move"

    # batch_payment_state = fields.Selection(
    #     [
    #         ("not_paid", "Not Paid (Batch)"),
    #         ("paid", "Paid via Batch"),
    #     ],
    #     string="Batch Payment Status",
    #     default="not_paid",
    #     copy=False,
    #     tracking=True,
    # )

    # batch_payment_state = fields.Selection(
    #     [
    #         ("not_paid", "Not Paid (Batch)"),
    #         ("exported", "Exported to Sage"),  # ✅ ADD THIS
    #         ("paid", "Paid via Batch"),
    #     ],
    #     string="Batch Payment Status",
    #     default="not_paid",
    #     copy=False,
    #     tracking=True,
    # )

    batch_payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('validated', 'Validated'),
        ('exported', 'Exported'),
        ('partial', 'Partial Paid'),
        ('paid', 'Paid'),
    ], default='not_paid', tracking=True)

    batch_payment_id = fields.Many2one(
        "batch.payment",
        string="Paid via Batch",
        copy=False,
        readonly=True,
    )

    is_paid_via_batch = fields.Boolean(
        compute="_compute_is_paid_via_batch",
        store=False
    )

    has_batch_payment = fields.Boolean(
        string="Has Batch Payment",
        default=False,
        copy=False,
    )

    hide_payment_buttons = fields.Boolean(
        compute="_compute_hide_payment_buttons",
        store=False,
    )
    #=======================partial=================
    amount_paid_batch = fields.Monetary(
        string="Batch Amount Paid",
        currency_field="currency_id",
        copy=False,
        default=0.0,
    )

    amount_outstanding_batch = fields.Monetary(
        string="Batch Outstanding",
        currency_field="currency_id",
        copy=False,
        default=0.0,
    )

    def _compute_hide_payment_buttons(self):
        for invoice in self:

            invoice.hide_payment_buttons = False

            payments = self.env['account.payment'].search([
                ('batch_invoice_id', '=', invoice.id)
            ])

            if not payments:
                continue

            lines = self.env['batch.payment.line'].search([
                ('payment_id', 'in', payments.ids)
            ])

            states = lines.mapped('batch_id.state')

            if 'draft' in states or 'validated' in states:
                invoice.hide_payment_buttons = True


    def _compute_is_paid_via_batch(self):
        for move in self:
            move.is_paid_via_batch = (
                    move.move_type in ("out_invoice", "in_invoice")
                    and move.batch_payment_state == "paid"
            )

    def action_register_payment_batch(self):
        self.ensure_one()
        action = self.action_register_payment()
        ctx = dict(action.get("context", {}) or {})
        ctx.update({"batch_skip_reconcile": True})
        action["context"] = ctx
        return action

    remaining_batch_amount = fields.Monetary(
        string="Remaining Batch Amount",
        compute="_compute_remaining_batch_amount",
        currency_field="currency_id",
        store=True,
    )

    @api.depends(
        "amount_total",
        "amount_paid_batch",
        "amount_outstanding_batch"
    )
    def _compute_remaining_batch_amount(self):

        for rec in self:

            if rec.batch_payment_state == "partial":

                rec.remaining_batch_amount = (
                    rec.amount_outstanding_batch
                )

            else:

                rec.remaining_batch_amount = (
                    rec.amount_total
                )
