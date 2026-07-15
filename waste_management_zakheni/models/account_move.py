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

    service_request_count = fields.Integer(
        compute="_compute_service_request_count"
    )
    service_request_name = fields.Char(
        string="Service Request",
        compute="_compute_service_request_name",
    )

    @api.depends("service_request_id")  # Use your actual field name here
    def _compute_service_request_name(self):
        for rec in self:
            rec.service_request_name = rec.service_request_id.name if rec.service_request_id else ""

    @api.depends("service_request_id")
    def _compute_service_request_count(self):
        for rec in self:
            rec.service_request_count = 1 if rec.service_request_id else 0

    def action_open_service_request(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Service Request",
            "res_model": "waste.service.request",
            "view_mode": "form",
            "res_id": self.service_request_id.id,
        }