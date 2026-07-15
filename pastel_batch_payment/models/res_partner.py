from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_reference = fields.Char(
        string="Customer Reference",
        required=True,
        copy=False,
        index=True,
        default="/",
    )

    @api.model_create_multi
    def create(self, vals_list):

        seq = self.env["ir.sequence"]

        for vals in vals_list:

            _logger.warning("BEFORE: %s", vals)

            if vals.get("customer_reference") in (False, "", "/"):
                vals["customer_reference"] = seq.next_by_code(
                    "customer.reference"
                )

            _logger.warning("AFTER: %s", vals)

        return super().create(vals_list)

    credit_ids = fields.One2many(
        "customer.credit",
        "partner_id",
    )

    credit_balance = fields.Monetary(
        compute="_compute_credit_balance",
        currency_field="currency_id",
        string="Credit Balance",
    )

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )

    @api.depends("credit_ids.balance")
    def _compute_credit_balance(self):
        for partner in self:
            partner.credit_balance = sum(
                partner.credit_ids.filtered(
                    lambda c: c.state == "open"
                ).mapped("balance")
            )

    credit_count = fields.Integer(
        compute="_compute_credit_count"
    )

    def _compute_credit_count(self):
        for partner in self:
            partner.credit_count = len(partner.credit_ids)