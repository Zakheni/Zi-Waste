from odoo import http
from odoo.http import request
import json

class MobileAPI(http.Controller):

    def _auth_user(self):
        auth = request.httprequest.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return None

        token = auth.replace("Bearer ", "")
        return request.env['res.users'].sudo().search([
            ('api_token', '=', token),
            ('active', '=', True)
        ], limit=1)

    @http.route('/api/mobile/test', type='http', auth='none', methods=['GET'], csrf=False)
    def test(self):
        return "MOBILE API OK"

    @http.route('/api/mobile/worksheets', type='http', auth='none', methods=['POST'], csrf=False)
    def worksheets(self):
        user = self._auth_user()
        if not user:
            return request.make_response(
                json.dumps({"success": False, "error": "Unauthorized"}),
                status=401,
                headers=[('Content-Type', 'application/json')]
            )

        Worksheet = request.env['waste.worksheet'].sudo()
        records = Worksheet.search([], limit=10)

        data = [{
            "id": w.id,
            "name": w.name,
            "state": w.state,
        } for w in records]

        return request.make_response(
            json.dumps({"success": True, "worksheets": data}),
            headers=[('Content-Type', 'application/json')]
        )
