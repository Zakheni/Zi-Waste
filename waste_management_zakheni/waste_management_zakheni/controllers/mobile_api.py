"""REST API endpoints for the Flutter mobile driver app."""

from odoo import http
from odoo.http import request
import json


class MobileAPI(http.Controller):
    """Bearer-token authenticated mobile endpoints for waste worksheets."""

    def _auth_user(self):
        """
        Authenticate the request via Authorization: Bearer <api_token>.

        Returns:
            res.users recordset or empty recordset when auth fails.
        """
        auth = request.httprequest.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return request.env['res.users']

        token = auth.replace("Bearer ", "").strip()
        return request.env['res.users'].sudo().search([
            ('api_token', '=', token),
            ('active', '=', True),
        ], limit=1)

    def _driver_employee(self, user):
        """
        Resolve the HR employee linked to the authenticated user.

        Returns:
            hr.employee record or empty recordset.
        """
        return request.env['hr.employee'].sudo().search([
            ('user_id', '=', user.id),
        ], limit=1)

    def _worksheet_domain_for_user(self, user):
        """
        Build a domain limiting worksheets to the logged-in driver.

        Returns:
            list: Odoo search domain for waste.worksheet.
        """
        partner = user.sudo().wmz_driver_partner_id
        if partner:
            return [('driver_id', '=', partner.id)]
        return [('id', '=', 0)]

    @http.route('/api/mobile/test', type='http', auth='none', methods=['GET'], csrf=False)
    def test(self):
        """Health-check endpoint for mobile connectivity."""
        return "MOBILE API OK"

    @http.route('/api/mobile/worksheets', type='http', auth='none', methods=['POST'], csrf=False)
    def worksheets(self):
        """
        List worksheets assigned to the authenticated driver.

        Returns:
            JSON response with success flag and worksheet summaries.
        """
        user = self._auth_user()
        if not user:
            return request.make_response(
                json.dumps({"success": False, "error": "Unauthorized"}),
                status=401,
                headers=[('Content-Type', 'application/json')],
            )

        Worksheet = request.env['waste.worksheet'].sudo()
        records = Worksheet.search(self._worksheet_domain_for_user(user), order='id desc', limit=50)

        data = [{
            "id": w.id,
            "name": w.name,
            "state": w.state,
            "service_request_id": w.service_request_id.id if w.service_request_id else False,
            "service_request_name": w.service_request_id.name if w.service_request_id else "",
        } for w in records]

        return request.make_response(
            json.dumps({"success": True, "worksheets": data}),
            headers=[('Content-Type', 'application/json')],
        )
