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





# from odoo import models, fields, api
# from odoo.exceptions import UserError
# from .service_provider import SA_PROVINCES  # same list used by wms.service.provider
#
#
# class WasteRequestProviderWizard(models.TransientModel):
#     _name = 'waste.request.provider.wizard'
#     _description = 'Find Service Provider for Waste Request'
#
#     # Link back to waste.service.request
#     request_id = fields.Many2one(
#         'waste.service.request',
#         string='Service Request',
#     )
#
#     # Search criteria
#     province = fields.Selection(
#         SA_PROVINCES,
#         string='Province',
#         required=True,
#     )
#     city = fields.Char(string='City', required=True)
#     suburb = fields.Char(string='Suburb')
#
#     # Result / manual choice
#     provider_id = fields.Many2one(
#         'wms.service.provider',
#         string='Service Provider',
#         help='Provider found from search or chosen manually.',
#     )
#
#     @api.model
#     def default_get(self, fields_list):
#         """
#         Prefill the wizard from the active waste.service.request if available.
#         """
#         res = super().default_get(fields_list)
#         ctx = self.env.context or {}
#         if ctx.get('active_model') == 'waste.service.request' and ctx.get('active_id'):
#             req = self.env['waste.service.request'].browse(ctx['active_id'])
#             res['request_id'] = req.id
#             # if the request already has a provider, show it
#             if req.provider_id:
#                 res['provider_id'] = req.provider_id.id
#         return res
#
#     def _search_provider_strong(self):
#         """Try exact province + city + suburb."""
#         domain = [
#             ('province', '=', self.province),
#             ('city', '=', self.city),
#         ]
#         if self.suburb:
#             domain.append(('suburb', '=', self.suburb))
#         return self.env['wms.service.provider'].search(domain, limit=1)
#
#     def _search_provider_relaxed(self):
#         """Try looser matches if the strong one fails."""
#         Provider = self.env['wms.service.provider']
#         # 1) province + city (ilike)
#         provider = Provider.search([
#             ('province', '=', self.province),
#             ('city', 'ilike', self.city),
#         ], limit=1)
#         if provider:
#             return provider
#
#         # 2) province + suburb (if suburb given)
#         if self.suburb:
#             provider = Provider.search([
#                 ('province', '=', self.province),
#                 ('suburb', 'ilike', self.suburb),
#             ], limit=1)
#             if provider:
#                 return provider
#
#         # 3) any provider in that province
#         provider = Provider.search([
#             ('province', '=', self.province),
#         ], limit=1)
#         if provider:
#             return provider
#
#         # 4) last fallback: any provider at all
#         return Provider.search([], limit=1)
#
#     def action_search_provider(self):
#         """
#         Main search button:
#         - Strong exact match first
#         - Then relaxed fallbacks
#         """
#         self.ensure_one()
#         if not self.province or not self.city:
#             raise UserError('Please fill in Province and City to search.')
#
#         provider = self._search_provider_strong()
#         if not provider:
#             provider = self._search_provider_relaxed()
#
#         if not provider:
#             raise UserError('No service provider found at all. Please create one first.')
#
#         self.provider_id = provider.id
#         return False  # stay in wizard, just fill the field
#
#     def action_apply_provider(self):
#         """
#         Apply selected provider to the waste.service.request and close.
#         """
#         self.ensure_one()
#
#         if not self.request_id:
#             raise UserError('No related service request found.')
#
#         if not self.provider_id:
#             raise UserError('Please select or search a service provider first.')
#
#         self.request_id.write({
#             'provider_id': self.provider_id.id,
#         })
#
#         return {'type': 'ir.actions.act_window_close'}
#


# from odoo import models, fields, api
# from odoo.exceptions import UserError
# from .service_provider import SA_PROVINCES  # same list used by wms.service.provider
#
#
# class WasteRequestProviderWizard(models.TransientModel):
#     _name = 'waste.request.provider.wizard'
#     _description = 'Find Service Provider for Waste Request'
#
#     # Link back to the calling waste.service.request
#     request_id = fields.Many2one(
#         'waste.service.request',
#         string='Service Request',
#     )
#
#     # Search criteria
#     province = fields.Selection(
#         SA_PROVINCES,
#         string='Province',
#         required=True,
#     )
#     city = fields.Char(string='City', required=True)
#     suburb = fields.Char(string='Suburb')
#
#     # Provider result / choice
#     provider_id = fields.Many2one(
#         'wms.service.provider',
#         string='Service Provider',
#         help='Provider found from search or chosen manually.',
#     )
#
#     @api.model
#     def default_get(self, fields_list):
#         """
#         Prefill wizard from the active waste.service.request if available.
#         """
#         res = super().default_get(fields_list)
#         ctx = self.env.context or {}
#         if ctx.get('active_model') == 'waste.service.request' and ctx.get('active_id'):
#             req = self.env['waste.service.request'].browse(ctx['active_id'])
#             res['request_id'] = req.id
#             # If request already has a provider, prefill provider_id
#             if req.provider_id:
#                 res['provider_id'] = req.provider_id.id
#             # You can also prefill location here if you later add those fields to request
#         return res
#
#     def action_search_provider(self):
#         """
#         Search provider in wms.service.provider using province, city, suburb.
#         Sets provider_id if found; otherwise raises error.
#         """
#         self.ensure_one()
#         if not self.province or not self.city:
#             raise UserError('Please fill in Province and City to search.')
#
#         domain = [
#             ('province', '=', self.province),
#             ('city', 'ilike', self.city),
#         ]
#         if self.suburb:
#             domain.append(('suburb', 'ilike', self.suburb))
#
#         provider = self.env['wms.service.provider'].search(domain, limit=1)
#         if not provider:
#             raise UserError('No service provider found for the given location.')
#         self.provider_id = provider.id
#         return False  # stay in the wizard
#
#     def action_apply_provider(self):
#         """
#         Apply selected/found provider to the waste.service.request and close.
#         """
#         self.ensure_one()
#         if not self.request_id:
#             raise UserError('No related service request found.')
#         if not self.provider_id:
#             raise UserError('Please select or search a service provider first.')
#
#         self.request_id.write({
#             'provider_id': self.provider_id.id,
#         })
#         return {'type': 'ir.actions.act_window_close'}
