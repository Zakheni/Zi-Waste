"""User-level theme preferences for company_smart_theme."""

from odoo import fields, models


class ResUsers(models.Model):
    """Extend users with an optional personal theme color override."""

    _inherit = "res.users"

    theme_color = fields.Char(string="Theme Color", default="#2C3E50")
