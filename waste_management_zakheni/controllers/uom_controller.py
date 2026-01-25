from odoo import http
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)

class UomController(http.Controller):

    @http.route(
        '/api/uoms',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def get_uoms(self):
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
        uoms = request.env['uom.uom'].sudo().search([])
        return json.dumps([
            {'id': u.id, 'name': u.name}
            for u in uoms
        ])

    @http.route('/ping_test', auth='public', type='http')
    def ping_test(self):
        return "PING OK"