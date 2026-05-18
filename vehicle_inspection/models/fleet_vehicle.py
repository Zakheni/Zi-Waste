from odoo import models, fields


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    is_vehicle_available = fields.Boolean(
        string="Available For Manifest",
        default=True
    )