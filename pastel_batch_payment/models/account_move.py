from odoo import models,fields


class AccountMove(models.Model):
    _inherit = "account.move"

    # batch_force_paid = fields.Boolean(
    #     string="Paid via Batch",
    #     default=False,
    #     copy=False,
    # )

    # def _compute_payment_state(self):
    #     super()._compute_payment_state()
    #     for move in self:
    #         if move.batch_force_paid:
    #             move.payment_state = 'paid'

    batch_payment_state = fields.Selection(
        [
            ("not_paid", "Not Paid (Batch)"),
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


