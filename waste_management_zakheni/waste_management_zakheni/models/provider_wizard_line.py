"""Transient lines for ranked service provider candidates."""
from odoo import fields, models


class WasteRequestProviderWizardLine(models.TransientModel):
    _name = "waste.request.provider.wizard.line"
    _description = "Service Provider Candidate"
    _order = "rank asc, distance_km asc"

    wizard_id = fields.Many2one(
        "waste.request.provider.wizard",
        required=True,
        ondelete="cascade",
    )
    provider_id = fields.Many2one("wms.service.provider", required=True)
    provider_name = fields.Char(related="provider_id.name")
    provider_address = fields.Text(related="provider_id.full_address", string="Location")
    provider_city = fields.Char(related="provider_id.city")
    provider_phone = fields.Char(related="provider_id.phone")
    distance_km = fields.Float(string="Distance (km)", digits=(10, 2))
    rank = fields.Integer(string="#")
    latitude = fields.Float(related="provider_id.latitude")
    longitude = fields.Float(related="provider_id.longitude")

    def action_select(self):
        """Select this provider on the wizard."""
        self.ensure_one()
        self.wizard_id.write({"provider_id": self.provider_id.id})
        self.wizard_id._sync_map_data()
        return {
            "type": "ir.actions.act_window",
            "res_model": "waste.request.provider.wizard",
            "res_id": self.wizard_id.id,
            "view_mode": "form",
            "target": "new",
        }
