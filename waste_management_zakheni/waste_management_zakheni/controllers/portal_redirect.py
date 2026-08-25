"""Portal home redirect — send client agents to the waste dashboard."""
from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class WastePortalRedirect(CustomerPortal):
    """Override /my to land agents on /my/waste."""

    @http.route(['/my'], type='http', auth='user', website=True)
    def portal_my_home(self, **kw):
        """Redirect client agents from /my to the waste portal home."""

        _logger.warning("PORTAL REDIRECT RUNNING")

        if request.env.user.has_group('waste_management_zakheni.group_wmz_client_agent'):
            return request.redirect('/my/waste')

        return super().portal_my_home(**kw)