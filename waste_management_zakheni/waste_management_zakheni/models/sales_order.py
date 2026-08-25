"""Sale order extensions linking manifests to customer quotes."""
from odoo import models, fields, api, _
from odoo.exceptions import (ValidationError)
from odoo.exceptions import UserError, AccessDenied, ValidationError
import re

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'

class SaleOrder(models.Model):
    """Link sale orders to waste service requests and pickup points."""
    _inherit = 'sale.order'

    # def unlink(self):
    #     if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
    #         raise UserError(_("You are not allowed to sale order."))
    #     return super().unlink()

    service_request_id = fields.Many2one(
        'waste.service.request',
        string="Manifest",
        ondelete="set null"

    )


    partner_id = fields.Many2one(
        'res.partner',
        string="Customer",
        required=True,
        domain="['&', ('is_company', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    planned_date = fields.Datetime(
        string="Planned Date",
        related="service_request_id.planned_date",
        store=True,
        readonly=True
    )

    pickup_point_id = fields.Many2one(
        'pickup.point',
        string="Drop-off/Pickup Point",
        domain="[('partner_id', '=', partner_id)]",

    )

    container_ids = fields.One2many('waste.container', 'sale_order_id', string="Waste Containers")

    service_request_name = fields.Char(
        compute="_compute_service_request_name"
    )

    @api.depends("service_request_id")
    def _compute_service_request_name(self):
        """Expose the linked manifest reference on the sale order."""
        for order in self:
            order.service_request_name = order.service_request_id.name or ""

    service_request_count = fields.Integer(
        compute='_compute_service_request_count'
    )

    def _compute_service_request_count(self):
        """Return 1 when a manifest is linked, else 0."""
        for order in self:
            order.service_request_count = 1 if order.service_request_id else 0

    def action_open_service_request(self):
        """Open the linked waste service request form."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Service Request',
            'res_model': 'waste.service.request',
            'view_mode': 'form',
            'res_id': self.service_request_id.id,
            'target': 'current',
        }

    @api.constrains('partner_id')
    def _check_not_own_company_partner(self):
        """Block invoicing the operating company as customer."""
        for rec in self:
            if rec.partner_id == rec.company_id.partner_id:
                raise ValidationError("You cannot invoice your own company.")


