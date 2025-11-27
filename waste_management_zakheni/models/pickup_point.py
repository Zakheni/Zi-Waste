from odoo import models, fields

class PickupPoint(models.Model):
    _name = 'pickup.point'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Pickup Point'

    name = fields.Char(string="Pickup Point Name", required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string="Customer", ondelete='cascade', tracking=True)
    container_ids = fields.One2many('waste.container', 'pickup_point_id', string="Waste Containers", tracking=True)
    sale_order_id = fields.Many2one('sale.order', string="Sales Order", tracking=True)

    service_request_id = fields.Many2one('waste.service.request', string="Request")
    pickup_request_id = fields.Many2one('waste.service.request')
    dropoff_request_id = fields.Many2one('waste.service.request')
