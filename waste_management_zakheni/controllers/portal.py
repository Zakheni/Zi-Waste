from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class WastePortalRedirect(CustomerPortal):

    @http.route(['/my', '/my/home'], type='http', auth="user", website=True, inherit=True)
    def portal_my_home(self, **kw):
        user = request.env.user

        _logger.info("PORTAL REDIRECT CHECK: %s", user.login)

        if user.has_group('waste_management_zakheni.group_wmz_client_agent'):
            return request.redirect('/my/waste')

        return super().portal_my_home(**kw)