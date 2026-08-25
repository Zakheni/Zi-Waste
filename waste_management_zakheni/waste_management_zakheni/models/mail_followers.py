"""Chatter follower formatting safe under POPIA company isolation."""
from odoo import models


class MailFollowers(models.Model):
    """Expose follower display names without requiring cross-company partner read."""
    _inherit = 'mail.followers'

    def _format_for_chatter(self):
        """Use sudo for partner display — POPIA hides other companies' contacts."""
        result = []
        for follower in self:
            partner = follower.partner_id.sudo()
            result.append({
                'id': follower.id,
                'partner_id': partner.id,
                'name': follower.name,
                'display_name': follower.display_name,
                'email': follower.email,
                'is_active': follower.is_active,
                'partner': partner.mail_partner_format()[partner],
            })
        return result
