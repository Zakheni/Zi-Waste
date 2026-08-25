"""Settings: Sage backend is configured on sage.backend, not here."""

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """Link to Sage Connector backend from Accounting settings."""

    _inherit = "res.config.settings"

    sage_backend_id = fields.Many2one(
        "sage.backend",
        string="Sage Backend",
        compute="_compute_sage_backend",
    )

    @api.depends("company_id")
    def _compute_sage_backend(self):
        Backend = self.env["sage.backend"]
        for rec in self:
            rec.sage_backend_id = Backend.search(
                [("company_id", "=", rec.company_id.id)], limit=1
            )
