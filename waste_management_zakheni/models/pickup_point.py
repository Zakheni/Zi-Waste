from odoo import models, fields, api


class PickupPoint(models.Model):
    _name = 'pickup.point'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Pickup Point'

    name = fields.Char(string="Pickup Point Name", required=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner',
        string="Customer",
        ondelete='cascade',
        tracking=True,
        domain="['&', ('is_company', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    container_ids = fields.One2many('waste.container', 'pickup_point_id', string="Waste Containers", tracking=True)
    sale_order_id = fields.Many2one('sale.order', string="Sales Order", tracking=True)

    service_request_id = fields.Many2one('waste.service.request', string="Request")
    pickup_request_id = fields.Many2one('waste.service.request')
    dropoff_request_id = fields.Many2one('waste.service.request')

    created_from_portal = fields.Boolean(default=False, readonly=True)
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        index=True
    )

    def _log_audit(self, message):
        self.env['mail.message'].sudo().create({
            'model': self._name,
            'res_id': self.id,
            'message_type': 'notification',
            'body': message,
            'author_id': self.env.user.partner_id.id,
        })

    @api.model
    def create(self, vals):
        if not vals.get('company_id'):
            vals['company_id'] = self.env.company.id
        return super().create(vals)
