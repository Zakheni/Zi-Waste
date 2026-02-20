from odoo import models, fields


class VehicleInspectionItem(models.Model):
    _name = "vehicle.inspection.item"
    _description = "Vehicle Inspection Item"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    category_id = fields.Many2one("vehicle.inspection.category", required=True, ondelete="cascade", tracking=True)
    require_photo = fields.Boolean(string="Photo Required", tracking=True)
    active = fields.Boolean(default=True, tracking=True)


