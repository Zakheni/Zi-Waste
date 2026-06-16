from odoo import models,fields


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

    batch_payment_state = fields.Selection(
        [
            ("not_paid", "Not Paid (Batch)"),
            ("exported", "Exported to Sage"),  # ✅ ADD THIS
            ("paid", "Paid via Batch"),
        ],
        string="Batch Payment Status",
        default="not_paid",
        copy=False,
        tracking=True,
    )

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


    # has_batch_payment = fields.Boolean(
    #     compute="_compute_has_batch_payment",
    #     store=False,
    # )
    #
    # def _compute_has_batch_payment(self):
    #     Payment = self.env['account.payment']
    #
    #     for invoice in self:
    #         invoice.has_batch_payment = bool(
    #             Payment.search_count([
    #                 ('batch_invoice_id', '=', invoice.id)
    #             ])
    #         )

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


