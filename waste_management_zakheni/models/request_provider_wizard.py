from odoo import models, fields, api
from odoo.exceptions import UserError
from .service_provider import SA_PROVINCES   # same list you used in wms.service.provider


class WasteRequestProviderWizard(models.TransientModel):
    _name = 'waste.request.provider.wizard'
    _description = 'Find Service Provider for Waste Request'

    # Link back to the calling waste.service.request
    request_id = fields.Many2one(
        'waste.service.request',
        string='Service Request',
    )

    # Search criteria
    province = fields.Selection(
        SA_PROVINCES,
        string='Province',
    )
    city = fields.Char(string='City')
    suburb = fields.Char(string='Suburb')

    # Result / manual choice
    provider_id = fields.Many2one(
        'wms.service.provider',
        string='Service Provider',
        help='Provider found from search or chosen manually.',
    )

    @api.model
    def default_get(self, fields_list):
        """Prefill the wizard with the active request (if any)."""
        res = super().default_get(fields_list)
        ctx = self.env.context or {}
        if ctx.get('active_model') == 'waste.service.request' and ctx.get('active_id'):
            req = self.env['waste.service.request'].browse(ctx['active_id'])
            res['request_id'] = req.id
        return res

    def action_search_provider(self):
        """
        Very forgiving search:
          1) Try using the filters province/city/suburb (if set)
          2) If nothing, fall back to ANY provider
        Also shows a notification so we know the method really executed.
        """
        self.ensure_one()
        Provider = self.env['wms.service.provider']

        domain = []
        if self.province:
            domain.append(('province', '=', self.province))
        if self.city:
            domain.append(('city', 'ilike', self.city))
        if self.suburb:
            domain.append(('suburb', 'ilike', self.suburb))

        if domain:
            provider = Provider.search(domain, limit=1)
        else:
            provider = Provider.search([], limit=1)

        if not provider:
            raise UserError("No service provider found in wms.service.provider. "
                            "Please create at least one service provider first.")

        # Set the provider on the wizard
        self.provider_id = provider.id

        # Show a notification so you SEE that the method ran
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Provider selected",
                "message": f"Using provider: {provider.name}",
                "sticky": False,
            },
        }

    def action_apply_provider(self):
        """
        Apply selected provider to waste.service.request and close.
        """
        self.ensure_one()
        if not self.request_id:
            raise UserError('No related service request found.')
        if not self.provider_id:
            raise UserError('Please search or select a provider first.')

        self.request_id.write({
            'provider_id': self.provider_id.id,
        })

        return {'type': 'ir.actions.act_window_close'}

