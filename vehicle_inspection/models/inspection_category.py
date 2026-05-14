from odoo import models, fields


class VehicleInspectionCategory(models.Model):
    _name = "vehicle.inspection.category"
    _description = "Vehicle Inspection Category"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
