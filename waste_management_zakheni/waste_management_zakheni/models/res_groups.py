from odoo import api, models


class ResGroups(models.Model):
    _inherit = 'res.groups'

    @api.model
    def refresh_user_groups_access_view(self):
        """Rebuild Settings → Users access-rights fields after group category changes."""
        self.sudo().with_context(
            install_filename=False,
            module=None,
        )._update_user_groups_view()
        self.env.registry.clear_cache()

    def _register_hook(self):
        super()._register_hook()
        # Keep the dynamic res.users access-rights view in sync after restarts/upgrades.
        self.refresh_user_groups_access_view()
