from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError
import psycopg2


class AccountMove(models.Model):
    _inherit = "account.move"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sales Order",
        compute="_compute_sale_order_id",
        store=True,
        readonly=True,
    )

    from odoo import models, _
    from odoo.exceptions import UserError

    class AccountMove(models.Model):
        _inherit = 'account.move'

        def unlink(self):
            if (
                    self.env.user.has_group('waste_management_zakheni.group_wmz_admin')
                    or
                    self.env.user.has_group('waste_management_zakheni.group_wmz_finance')
            ):
                raise UserError(_("You are not allowed to delete invoices."))

            return super(AccountMove, self).unlink()



    service_request_id = fields.Many2one(
        "waste.service.request",
        string="Manifest",
        compute="_compute_service_request_id",
        store=True,
        readonly=True,
        index=True,
    )

    @api.depends("invoice_line_ids.sale_line_ids.order_id")
    def _compute_sale_order_id(self):
        for move in self:
            orders = move.invoice_line_ids.sale_line_ids.order_id
            move.sale_order_id = orders[:1].id if orders else False

    @api.depends("sale_order_id.service_request_id")
    def _compute_service_request_id(self):
        for move in self:
            move.service_request_id = move.sale_order_id.service_request_id if move.sale_order_id else False