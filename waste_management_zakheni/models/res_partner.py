from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    pickup_point_ids = fields.One2many(
        'pickup.point', 'partner_id', string='Pickup Points'
    )

    wmz_use_company_config = fields.Boolean(
        string="Use Company Service Configuration",
        default=True,
        help="If enabled, this customer inherits services/container types from the company."
    )

    wmz_service_ids = fields.Many2many(
        "service.request",
        "wmz_partner_service_rel",
        "partner_id",
        "service_id",
        string="Waste Services for Company",
        help="Service offerings this client company uses."
    )

    wmz_container_type_ids = fields.Many2many(
        "container.type",
        "wmz_partner_container_type_rel",
        "partner_id",
        "container_type_id",
        string="Container Types for Company",
        help="Container types (Bins/Tanks) this client company uses."
    )

    wmz_waste_type_ids = fields.Many2many(
        "waste.type",
        "wmz_partner_waste_type_rel",
        "partner_id",
        "waste_type_id",
        string="Waste Types for Company",
        help="Waste types this company collected."
    )

