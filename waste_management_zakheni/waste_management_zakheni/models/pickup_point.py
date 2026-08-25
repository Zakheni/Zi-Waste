"""Customer pickup and drop-off locations for waste service requests."""
from odoo import models, fields, api, _


class PickupPoint(models.Model):
    """Named site where bins are placed, lifted, or tanks are serviced."""
    _name = 'pickup.point'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Pickup Point'

    name = fields.Char(string="Pickup Point Name", required=True, tracking=True)

    # partner_id = fields.Many2one(
    #     'res.partner',
    #     string="Customer",
    #     ondelete='cascade',
    #     tracking=True,
    #     domain="['&', ('is_company', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    # )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        tracking=True,
        domain="['&', ('is_company', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    container_count = fields.Integer(
        string="Containers",
        compute="_compute_container_count",
    )

    container_ids = fields.One2many('waste.container', 'pickup_point_id', string="Waste Containers", tracking=True)
    sale_order_id = fields.Many2one('sale.order', string="Sales Order", tracking=True)

    service_request_id = fields.Many2one('waste.service.request', string="Request")
    pickup_request_id = fields.Many2one('waste.service.request')
    dropoff_request_id = fields.Many2one('waste.service.request')

    created_from_portal = fields.Boolean(default=False, readonly=True)
    active = fields.Boolean(default=True)

    # company_id = fields.Many2one(
    #     'res.company',
    #     string='Company',
    #     index=True
    # )
    company_id = fields.Many2one(
        "res.company",
        required=False,
        default=lambda self: self.env.company,
        index=True,
    )

    @api.depends("container_ids")
    def _compute_container_count(self):
        for point in self:
            point.container_count = len(point.container_ids)

    def action_view_containers(self):
        """Open waste containers linked to this pickup point."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Containers"),
            "res_model": "waste.container",
            "view_mode": "tree,form",
            "domain": [("pickup_point_id", "=", self.id)],
            "context": {
                "default_pickup_point_id": self.id,
                "default_partner_id": self.partner_id.id,
            },
        }

    def _log_audit(self, message):
        """Post an audit notification to the pickup point chatter."""
        self.env['mail.message'].sudo().create({
            'model': self._name,
            'res_id': self.id,
            'message_type': 'notification',
            'body': message,
            'author_id': self.env.user.partner_id.id,
        })

    @api.model
    def create(self, vals):
        """Default company to the current user company on create."""
        if not vals.get('company_id'):
            vals['company_id'] = self.env.company.id
        return super().create(vals)
