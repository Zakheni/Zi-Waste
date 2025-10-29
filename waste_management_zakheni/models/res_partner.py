from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    pickup_point_ids = fields.One2many(
        'pickup.point', 'partner_id', string='Pickup Points'
    )
