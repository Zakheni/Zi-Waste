"""Signup controller — assign WMZ portal groups on self-registration."""
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class WmzSignup(AuthSignupHome):
    """Extend auth signup to set customer or agent portal groups."""

    def signup_allowed_fields(self):
        """Include wmz_portal_group in permitted signup form fields."""
        fields = super().signup_allowed_fields()
        fields.add('wmz_portal_group')
        return fields

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_signup(self, **kw):
        """Override the actual signup route"""
        _logger.error("WMZ web_signup HIT")
        return super().web_signup(**kw)

    def do_signup(self, qcontext):
        """Complete signup and assign WMZ customer or agent portal group."""
        _logger.error("WMZ do_signup HIT")
        _logger.error("SIGNUP CONTEXT: %s", qcontext)
        _logger.error("REQUEST PARAMS: %s", request.params)

        response = super().do_signup(qcontext)

        user = request.env.user
        role = request.params.get('wmz_portal_group')

        _logger.error("NEW USER: %s (%s)", user.login, user.id)
        _logger.error("ROLE RECEIVED: %s", role)

        if role == 'customer':
            group = request.env.ref(
                'waste_management_zakheni.group_wmz_client_customer'
            )
            user.sudo().write({'groups_id': [(4, group.id)]})
            _logger.error("CUSTOMER GROUP ASSIGNED")

        elif role == 'agent':
            group = request.env.ref(
                'waste_management_zakheni.group_wmz_client_agent'
            )
            user.sudo().write({'groups_id': [(4, group.id)]})
            _logger.error("AGENT GROUP ASSIGNED")

        else:
            _logger.error("NO ROLE SELECTED")

        return response
