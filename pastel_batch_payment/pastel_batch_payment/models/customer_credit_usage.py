"""Audit trail of customer credit applied to batch payments."""

from odoo import models, fields


class CustomerCreditUsage(models.Model):
    """Record each application of customer credit to a batch payment."""

    _name = "customer.credit.usage"
    _description = "Customer Credit Usage"
    _order = "create_date desc"

    credit_id = fields.Many2one(
        "customer.credit",
        required=True,
        ondelete="cascade"
    )

    partner_id = fields.Many2one(
        "res.partner",
        related="credit_id.partner_id",
        store=True
    )

    source_batch_id = fields.Many2one(
        "batch.payment",
        string="Credit Source Batch"
    )

    applied_batch_id = fields.Many2one(
        "batch.payment",
        string="Applied To Batch"
    )

    amount = fields.Monetary()

    currency_id = fields.Many2one(
        "res.currency",
        required=True
    )

    user_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user
    )