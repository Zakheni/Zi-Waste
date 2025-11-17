from odoo import api, fields, models, _
from .service_provider import SA_PROVINCES

class ServiceProviderSelectWizard(models.TransientModel):
    _name = "wms.service.provider.select.wizard"
    _description = "Find/Select Best Service Provider"

    # inputs
    province = fields.Selection(SA_PROVINCES, required=True, default="WC")
    city = fields.Char(required=True)
    suburb = fields.Char()
    # models/provider_wizard.py
    required_category_ids = fields.Many2many(
        "fleet.vehicle.model.category",
        "wms_wiz_req_cat_rel",  # short relation table name
        "wizard_id",
        "category_id",
        string="Required Fleet Categories",
        help="Providers must have all selected categories.",
    )

    # output
    provider_id = fields.Many2one("wms.service.provider", string="Suggested Provider", readonly=True)

    def action_find(self):
        self.ensure_one()
        category_ids = self.required_category_ids.ids if self.required_category_ids else False
        provider_id = self.env["wms.service.provider"].find_best_provider(
            self.province, self.city, self.suburb, category_ids
        )
        if provider_id:
            self.provider_id = provider_id
            return {
                "type": "ir.actions.act_window",
                "name": _("Suggested Provider"),
                "res_model": "wms.service.provider",
                "res_id": provider_id,
                "view_mode": "form",
                "target": "current",
            }
        else:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No provider found"),
                    "message": _("No provider matched your criteria."),
                    "sticky": False,
                },
            }


#
# from odoo import api, fields, models, _
# from .service_provider import SA_PROVINCES
#
# class ServiceProviderSelectWizard(models.TransientModel):
#     _name = "wms.service.provider.select.wizard"
#     _description = "Find/Select Best Service Provider"
#
#     # inputs
#     province = fields.Selection(SA_PROVINCES, required=True, default="WC")
#     city = fields.Char(required=True)
#     suburb = fields.Char()
#
#     required_category_ids = fields.Many2many(
#         "fleet.vehicle.model.category",
#         "wms_wiz_req_cat_rel",  # short relation table name
#         "wizard_id",
#         "category_id",
#         string="Required Fleet Categories",
#         help="Providers must have all selected categories.",
#     )
#
#     # output
#     provider_id = fields.Many2one(
#         "wms.service.provider",
#         string="Suggested Provider",
#         readonly=True,
#     )
#
#     def action_find(self):
#         self.ensure_one()
#
#         category_ids = self.required_category_ids.ids if self.required_category_ids else False
#
#         provider_id = self.env["wms.service.provider"].find_best_provider(
#             self.province, self.city, self.suburb, category_ids
#         )
#
#         if provider_id:
#             # set the field so it shows in the wizard
#             self.provider_id = provider_id
#             # IMPORTANT: do NOT redirect to another form
#             # just return nothing / True to stay on the wizard
#             return True
#         else:
#             # no provider found -> show notification and stay on the wizard
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {
#                     "title": _("No provider found"),
#                     "message": _("No provider matched your criteria."),
#                     "sticky": False,
#                 },
#             }
#
#
#     def action_open_provider(self):
#         self.ensure_one()
#         if not self.provider_id:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {
#                     "title": _("No provider selected"),
#                     "message": _("Please click 'Find Provider' first."),
#                     "sticky": False,
#                 },
#             }
#         return {
#             "type": "ir.actions.act_window",
#             "name": _("Suggested Provider"),
#             "res_model": "wms.service.provider",
#             "view_mode": "form",
#             "res_id": self.provider_id.id,
#             "target": "current",
#         }
#

#

