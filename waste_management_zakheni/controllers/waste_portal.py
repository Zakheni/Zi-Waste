from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
import base64


class WasteClientPortal(CustomerPortal):
    """
    Portal controller for Waste Service Requests + Worksheets.
    """

    # ------------------------------------------------------------
    # HOME: add counters for tiles
    # ------------------------------------------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)

        WasteRequest = request.env['waste.service.request']
        user = request.env.user

        # Agents: see all; Customers: only their own
        if user.has_group('waste_management_zakheni.group_wmz_client_agent'):
            domain = []
        else:
            domain = [('partner_id', '=', user.partner_id.id)]

        request_count = WasteRequest.sudo().search_count(domain)
        values['waste_request_count'] = request_count or 0

        return values

    # ------------------------------------------------------------
    # LIST: View Logged Requests
    # ------------------------------------------------------------
    @http.route(['/my/waste/requests'], type='http', auth='user', website=True)
    def portal_my_waste_requests(self, **kw):
        user = request.env.user
        WasteRequest = request.env['waste.service.request']

        if user.has_group('waste_management_zakheni.group_wmz_client_agent'):
            domain = []
        else:
            domain = [('partner_id', '=', user.partner_id.id)]

        wsr = WasteRequest.sudo().search(domain, order="create_date desc")

        values = {
            'page_name': 'waste_requests',
            'wsr_records': wsr,
        }
        return request.render('waste_management_zakheni.portal_my_waste_requests', values)

    # ------------------------------------------------------------
    # FORM: Log Service Request (GET)
    # ------------------------------------------------------------
    @http.route('/my/waste/request/new', type='http', auth='user', website=True)
    def portal_new_waste_request_form(self, **kwargs):
        partner = request.env.user.partner_id
        env = request.env

        values = {
            'page_name': 'waste_new_request',
            'csrf_token': request.csrf_token(),

            'pickup_points': env['pickup.point'].sudo().search([('partner_id', '=', partner.id)]),
            'container_types': env['container.type'].sudo().search([]),
            'bin_types': env['bin.type'].sudo().search([]),
            'tank_volumes': env['tank.volume'].sudo().search([]),

            'services': env['service.request'].sudo().search([]),
            'waste_types': env['waste.type'].sudo().search([]),
            'waste_details': env['waste.details'].sudo().search([]),
        }
        return request.render(
            'waste_management_zakheni.portal_new_waste_request_form',
            values
        )

    # ------------------------------------------------------------
    # FORM: Log Service Request (POST)
    # ------------------------------------------------------------
    @http.route(
        '/my/waste/request/create',
        type='http',
        auth='user',
        website=True,
        methods=['POST']
    )
    def portal_create_waste_request(self, **post):
        partner = request.env.user.partner_id
        env = request.env

        # pick-up point (single) mapped to m2m
        pickup_point_ids = []
        if post.get('pickup_point_id'):
            pickup_point_ids = [int(post.get('pickup_point_id'))]

        # container type string -> container_type_id
        container_type_id = False
        ctype = post.get('container_type')  # 'bin' or 'tank'
        if ctype == 'bin':
            ct = env['container.type'].sudo().search([('name', '=', 'Bin')], limit=1)
            container_type_id = ct.id
        elif ctype == 'tank':
            ct = env['container.type'].sudo().search([('name', '=', 'Tank')], limit=1)
            container_type_id = ct.id

        vals = {
            'partner_id': partner.id,
            'ticket_type': post.get('ticket_type') or 'pickup',
            'service_description': post.get('service_description'),

            'pickup_point_ids': [(6, 0, pickup_point_ids)],

            'container_type_id': container_type_id or False,
        }

        # bin / tank size
        if ctype == 'bin' and post.get('bin_type_id'):
            vals['bin_type_id'] = int(post.get('bin_type_id'))
            vals['tank_volume_id'] = False
        elif ctype == 'tank' and post.get('tank_volume_id'):
            vals['tank_volume_id'] = int(post.get('tank_volume_id'))
            vals['bin_type_id'] = False

        # service & waste relations
        if post.get('service_requested_id'):
            vals['service_requested_id'] = int(post.get('service_requested_id'))
        if post.get('waste_type_id'):
            vals['waste_type_id'] = int(post.get('waste_type_id'))
        if post.get('waste_details_id'):
            vals['waste_details_id'] = int(post.get('waste_details_id'))

        wsr = env['waste.service.request'].sudo().create(vals)
        return request.redirect('/my/waste/request/thankyou/%s' % wsr.id)

    # ------------------------------------------------------------
    # THANK YOU PAGE
    # ------------------------------------------------------------
    @http.route(
        ['/my/waste/request/thankyou/<int:wsr_id>'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_waste_request_thankyou(self, wsr_id, **kw):
        wsr = request.env['waste.service.request'].sudo().browse(wsr_id)
        if not wsr.exists():
            return request.not_found()

        user = request.env.user
        if not user.has_group('waste_management_zakheni.group_wmz_client_agent'):
            if wsr.partner_id.id != user.partner_id.id:
                return request.not_found()

        values = {
            'page_name': 'waste_request_thankyou',
            'wsr': wsr,
        }
        return request.render('waste_management_zakheni.portal_waste_request_thankyou', values)

    # ------------------------------------------------------------
    # DETAIL VIEW: Service Request + Worksheets list
    # ------------------------------------------------------------
    @http.route(
        ['/my/waste/request/<int:wsr_id>'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_waste_request_detail(self, wsr_id, **kw):
        WasteRequest = request.env['waste.service.request'].sudo()
        Worksheet = request.env['waste.worksheet'].sudo()

        wsr = WasteRequest.browse(wsr_id)
        if not wsr.exists():
            return request.not_found()

        user = request.env.user
        if not user.has_group('waste_management_zakheni.group_wmz_client_agent'):
            if wsr.partner_id.id != user.partner_id.id:
                return request.not_found()

        worksheets = Worksheet.search([
            ('service_request_id', '=', wsr.id)
        ], order='create_date desc')

        values = {
            'page_name': 'waste_request_detail',
            'wsr': wsr,
            'worksheets': worksheets,
            # 🔽 NEW:
            'portal_msg': kw.get('msg'),
        }
        return request.render('waste_management_zakheni.portal_waste_request_detail', values)

    # ------------------------------------------------------------
    # WORKSHEET FORM: open for editing
    # ------------------------------------------------------------
    @http.route(
        ['/my/waste/worksheet/<int:worksheet_id>/edit'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_waste_worksheet_edit(self, worksheet_id, **kw):
        Worksheet = request.env['waste.worksheet'].sudo()
        ws = Worksheet.browse(worksheet_id)
        if not ws.exists():
            return request.not_found()

        user = request.env.user

        # Portal customers: only allow access to their own worksheet,
        # via the linked service request's partner
        if not user.has_group('waste_management_zakheni.group_wmz_client_agent'):
            sr = ws.service_request_id
            if not sr or sr.partner_id.id != user.partner_id.id:
                return request.not_found()

        values = {
            'page_name': 'waste_worksheet_edit',
            'worksheet': ws,
            # pass the linked service request too (nice for breadcrumb)
            'wsr': ws.service_request_id,
            'csrf_token': request.csrf_token(),
        }
        return request.render('waste_management_zakheni.portal_waste_worksheet_form', values)


    @http.route(
        ['/my/waste/worksheet/<int:worksheet_id>/save'],
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
    )
    def portal_waste_worksheet_save(self, worksheet_id, **post):
        Worksheet = request.env['waste.worksheet'].sudo()
        ws = Worksheet.browse(worksheet_id)
        if not ws.exists():
            return request.not_found()

        user = request.env.user

        # 🔐 Security: only owner (or agent group) can save
        if not user.has_group('waste_management_zakheni.group_wmz_client_agent'):
            sr = ws.service_request_id
            if not sr or sr.partner_id.id != user.partner_id.id:
                return request.not_found()

        # --- helper: convert HTML datetime-local → Odoo format ---
        def _convert_dt(val):
            """
            HTML datetime-local: 'YYYY-MM-DDTHH:MM'
            Odoo expects:       'YYYY-MM-DD HH:MM:SS'
            """
            if not val:
                return False
            val = val.replace('T', ' ')
            if len(val) == 16:  # 'YYYY-MM-DD HH:MM'
                val = val + ':00'
            return val

        vals = {}

        # Dates
        arrival_raw = post.get('arrival_time')
        return_raw = post.get('return_date')

        if arrival_raw:
            vals['arrival_time'] = _convert_dt(arrival_raw)
        if return_raw:
            vals['return_date'] = _convert_dt(return_raw)

        # Simple numeric fields
        if post.get('kilometers'):
            try:
                vals['kilometers'] = int(post.get('kilometers'))
            except Exception:
                pass

        if post.get('quantity_collected'):
            try:
                vals['quantity_collected'] = float(post.get('quantity_collected'))
            except Exception:
                pass

        # Unit of measure
        if post.get('unit_of_measure'):
            try:
                vals['unit_of_measure'] = int(post.get('unit_of_measure'))
            except Exception:
                pass

        # Notes
        if post.get('notes_html'):
            vals['notes_html'] = post.get('notes_html')

        # You can also allow them to change state if you want, e.g. to 'done'
        # if post.get('state') in ['draft', 'in_progress', 'done']:
        #     vals['state'] = post.get('state')

        if vals:
            ws.write(vals)

        # Redirect back to the service request detail (portal page)
        return request.redirect('/my/waste/request/%s' % ws.service_request_id.id)

