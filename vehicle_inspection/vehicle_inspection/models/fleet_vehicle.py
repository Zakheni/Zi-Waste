"""Fleet vehicle extension for inspection availability tracking."""

from odoo import models, fields


class FleetVehicle(models.Model):
    """Extend fleet.vehicle with manifest availability status.

    The is_vehicle_available flag is toggled when inspections enter or
    leave the not_running state.
    """

    _inherit = "fleet.vehicle"

    is_vehicle_available = fields.Boolean(
        string="Available For Manifest",
        default=True
    )
