"""Public JSON API exposing units of measure for mobile clients."""
from odoo import http
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)

class UomController(http.Controller):
    """Read-only UoM list endpoints for Flutter integration."""

    @http.route(
        '/api/uoms',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def get_uoms(self):
        """Return all units of measure as JSON for mobile clients."""
        uoms = request.env['uom.uom'].sudo().search([])

        data = [
            {'id': u.id, 'name': u.name}
            for u in uoms
        ]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )\


    @http.route('/api/uoms_test', type='http', auth='public', methods=['GET'])
    def get_uoms_test(self):
        """Test endpoint returning UoM list as JSON string."""
        uoms = request.env['uom.uom'].sudo().search([])
        return json.dumps([
            {'id': u.id, 'name': u.name}
            for u in uoms
        ])

    @http.route('/ping_test', auth='public', type='http')
    def ping_test(self):
        """Simple health-check endpoint returning PING OK."""
        return "PING OK"