"""Re-sync company theme when the linked partner logo changes."""

from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def write(self, vals):
        res = super().write(vals)
        if "image_1920" in vals:
            companies = self.env["res.company"].sudo().search([
                ("partner_id", "in", self.ids),
                ("auto_theme_from_logo", "=", True),
            ])
            if companies:
                companies._sync_theme_from_logo()
        return res
