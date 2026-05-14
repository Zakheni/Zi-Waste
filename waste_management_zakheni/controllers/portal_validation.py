from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo import http, _
from odoo.http import request
import re

class PortalAccountPhoneValidation(CustomerPortal):

    @http.route(['/my/account'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def account(self, **post):

        # GET → keep default
        if request.httprequest.method == 'GET':
            return super().account(**post)

        partner = request.env.user.partner_id
        phone = (post.get('phone') or '').strip()

        # ❌ INVALID PHONE
        if phone and not re.match(r'^\+\d{7,15}$', phone):
            values = self._prepare_portal_layout_values()
            values.update({
                'partner': partner,
                'error': {'phone': True},   # 🔑 THIS FIXES EVERYTHING
            })
            return request.render('portal.portal_my_details', values)

        # ✅ VALID → normal behavior
        return super().account(**post)


# from odoo import http, _
# from odoo.http import request
# from odoo.exceptions import ValidationError
# import re
#
# class PortalAccountOverride(http.Controller):
#
#     @http.route('/my/account', type='http', auth='user', website=True, methods=['POST'])
#     def portal_my_account_post(self, **post):
#         partner = request.env.user.partner_id
#
#         phone = (post.get('phone') or '').strip()
#
#         # 🔒 Validate BEFORE write()
#         if phone and not re.match(r'^\+\d{7,15}$', phone):
#             values = {
#                 'error': _("Phone number must include country code, e.g. +27XXXXXXXXX"),
#                 'partner': partner,
#             }
#             return request.render('portal.portal_my_details', values)
#
#         # ✅ Safe write (model constraint still applies)
#         try:
#             partner.sudo().write({
#                 'phone': phone,
#                 'street': post.get('street'),
#                 'city': post.get('city'),
#                 'zip': post.get('zip'),
#                 'state_id': int(post.get('state_id') or 0) or False,
#                 'country_id': int(post.get('country_id') or 0) or False,
#             })
#         except ValidationError as e:
#             return request.render(
#                 'portal.portal_my_details',
#                 {
#                     'error': e.args[0],
#                     'partner': partner,
#                 }
#             )
#
#         return request.redirect('/my/account')
#

# from odoo import http, _
# from odoo.http import request
# # from odoo.exceptions import ValidationError
# import re
#
# class PortalValidation(http.Controller):
#
#     @http.route('/my/account', type='http', auth='user', website=True, methods=['POST'])
#     def portal_my_account_post(self, **post):
#         phone = (post.get('phone') or '').strip()
#
#         if phone and not re.match(r'^\+\d{7,15}$', phone):
#             return request.render(
#                 'portal.portal_my_details',
#                 {
#                     'error': _("Phone number must include country code, e.g. +27XXXXXXXXX"),
#                 }
#             )
#
#         return request.redirect('/my/account')
