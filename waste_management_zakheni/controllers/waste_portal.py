import json
from odoo import fields
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager
import base64


class WasteClientPortal(CustomerPortal):
    """
    Portal controller for Waste Service Requests + Worksheets.
    """

    AGENT_GROUP = 'waste_management_zakheni.group_wmz_client_agent'

    # ------------------------------------------------------------
    # HOME: add counters for tiles
    # ------------------------------------------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)

        WasteRequest = request.env['waste.service.request']
        user = request.env.user
        commercial_id = user.partner_id.commercial_partner_id.id

        if user.has_group(self.AGENT_GROUP):
            # Agent: own company + specific states
            domain = [
                ('state', 'in', [
                    'scheduled',
                    'dispatched',
                    'service_delivered',
                    'cancelled',
                    'done',
                ]),
                ('partner_id.commercial_partner_id', '=', commercial_id),
            ]
        else:
            # Customer: all requests under their commercial company
            domain = [
                ('partner_id.commercial_partner_id', '=', commercial_id),
            ]

        request_count = WasteRequest.sudo().search_count(domain)
        values['waste_request_count'] = request_count or 0

        return values

    # ------------------------------------------------------------
    # LIST: View Logged Requests
    # ------------------------------------------------------------
    @http.route(['/my/waste/requests'], type='http', auth='user', website=True)
    def portal_my_waste_requests(self, **kw):
        user = request.env.user
        WasteRequest = request.env['waste.service.request'].sudo()
        commercial_id = user.partner_id.commercial_partner_id.id

        # # base domain
        # if user.has_group(self.AGENT_GROUP):
        #     domain = [
        #         ('partner_id', 'child_of', commercial_id),
        #         ('state', 'in', ['scheduled', 'dispatched', 'service_delivered', 'cancelled', 'done']),
        #     ]
        if user.has_group(self.AGENT_GROUP):
            domain = [
                ('partner_id', 'child_of', commercial_id),
                ('state', 'in', ['scheduled', 'dispatched', 'service_delivered', 'cancelled', 'done']),
                # ✅ only show records that use a service provider
                ('is_service_provider', '=', True),
                # (optional but recommended) ensure provider is selected
                ('provider_id', '!=', False),
            ]

        else:
            # domain = [
            #     ('partner_id.commercial_partner_id', '=', commercial_id),
            # ]
            domain = [
                ('partner_id.commercial_partner_id', '=', commercial_id),
                ('is_service_provider', '=', True),
                ('provider_id', '!=', False),
            ]

        # apply state filter BEFORE search
        state = kw.get('state')
        if state == 'open':
            domain += [('state', 'not in', ['cancelled', 'done'])]
        elif state:
            domain += [('state', '=', state)]

        wsr = WasteRequest.search(domain, order="create_date desc")

        values = {
            'page_name': 'waste_requests',
            'wsr_records': wsr,
            'portal_msg': kw.get('msg'),
            'active_state': state,  # optional: to highlight active card/filter
        }
        return request.render('waste_management_zakheni.portal_my_waste_requests', values)

    @http.route('/my/waste/request/new', type='http', auth='user', website=True)
    def portal_new_waste_request_form(self, **kwargs):
        user = request.env.user

        # 🚫 Agents are not allowed to log requests
        if user.has_group(self.AGENT_GROUP):
            return request.redirect('/my/waste/requests?msg=agent_cannot_log')

        partner = user.partner_id
        env = request.env
        default_client_id = partner.commercial_partner_id.id

        client_companies = env['res.partner'].sudo().search(
            [
                ('is_company', '=', True),
                ('active', '=', True),
            ],
            order="name"
        )

        values = {
            'page_name': 'waste_new_request',
            'csrf_token': request.csrf_token(),

            # company list for dropdown
            'client_companies': client_companies,
            # 'default_client_id': partner.commercial_partner_id.id,
            'default_client_id': default_client_id,
            'pickup_points': env['pickup.point'].sudo().search([('partner_id', '=', default_client_id)],
                                                               order="name asc"),

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
        user = request.env.user
        # 🚫 Agents are not allowed to log requests
        if user.has_group(self.AGENT_GROUP):
            return request.redirect('/my/waste/requests?msg=agent_cannot_log')
        partner = user.partner_id
        env = request.env

        # 🔹 company/client from res.partner
        client_partner_id = partner.commercial_partner_id.id
        if post.get('client_partner_id'):
            try:
                client_partner_id = int(post.get('client_partner_id'))
            except Exception:
                client_partner_id = partner.commercial_partner_id.id

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
            'partner_id': client_partner_id,  # ✅ correct company
            'ticket_type': post.get('ticket_type') or 'pickup',
            'service_description': post.get('service_description'),
            'pickup_point_ids': [(6, 0, pickup_point_ids)],
            'container_type_id': container_type_id or False,
            'from_portal': True,
            'company_id': env.user.company_id.id,  # ✅ Internal company
        }
        # wsr = env['waste.service.request'].sudo().create(vals)

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

        # SEND EMAIL TO CUSTOMER (AND/OR INTERNAL) WHEN REQUEST IS LOGGED
        template = request.env.ref(
            "waste_management_zakheni.mail_tmpl_service_request_portal_completion",
            raise_if_not_found=False
        )
        if template:
            template.sudo().send_mail(wsr.id, force_send=True, raise_exception=False)

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
        user = request.env.user
        commercial_id = user.partner_id.commercial_partner_id.id

        if user.has_group(self.AGENT_GROUP):
            # Agent: own company + allowed states
            domain = [
                ('id', '=', wsr_id),
                ('partner_id.commercial_partner_id', '=', commercial_id),
                ('state', 'in', [
                    'scheduled',
                    'dispatched',
                    'service_delivered',
                    'cancelled',
                    'done',
                ]),
            ]
        else:
            # Customer: any request under their commercial company
            domain = [
                ('id', '=', wsr_id),
                ('partner_id.commercial_partner_id', '=', commercial_id),
            ]

        wsr = WasteRequest.search(domain, limit=1)
        if not wsr:
            return request.not_found()


        wsr_sudo = wsr.sudo()

        # -------- Customer & Service (display strings) ----------
        customer_name = wsr_sudo.partner_id.display_name or '-'
        service_requested_name = (
            wsr_sudo.service_requested_id.display_name
            if wsr_sudo.service_requested_id
            else '-'
        )
        waste_type_name = (
            wsr_sudo.waste_type_id.display_name
            if wsr_sudo.waste_type_id
            else '-'
        )
        waste_details_name = (
            wsr_sudo.waste_details_id.display_name
            if wsr_sudo.waste_details_id
            else '-'
        )

        container_type_name = (
            wsr_sudo.container_type_id.display_name
            if wsr_sudo.container_type_id
            else '-'
        )
        bin_type_name = (
            wsr_sudo.bin_type_id.display_name
            if wsr_sudo.bin_type_id
            else ''
        )
        tank_volume_name = (
            wsr_sudo.tank_volume_id.display_name
            if wsr_sudo.tank_volume_id
            else ''
        )

        # -------- Locations & Containers (display strings) ----------
        pickup_points_list = [
            (pp.display_name or '').strip()
            for pp in wsr_sudo.pickup_point_ids
        ]
        pickup_points_list = [p for p in pickup_points_list if p]

        dropoff_points_list = [
            (dp.display_name or '').strip()
            for dp in wsr_sudo.dropoff_point_ids
        ]
        dropoff_points_list = [d for d in dropoff_points_list if d]

        bins_summary_text = wsr_sudo.pickup_point_bins_summary or ''
        bin_line_count = wsr_sudo.bin_line_count or 0

        is_agent = user.has_group(self.AGENT_GROUP)
        worksheets = False
        if is_agent:
            worksheets = Worksheet.search(
                [('service_request_id', '=', wsr.id)],
                order='create_date desc'
            )

        values = {
            'page_name': 'waste_request_detail',
            'wsr': wsr,
            'worksheets': worksheets,
            'is_agent': is_agent,
            'portal_msg': kw.get('msg'),

            'customer_name': customer_name,
            'service_requested_name': service_requested_name,
            'waste_type_name': waste_type_name,
            'waste_details_name': waste_details_name,
            'container_type_name': container_type_name,
            'bin_type_name': bin_type_name,
            'tank_volume_name': tank_volume_name,
            'pickup_points_list': pickup_points_list,
            'dropoff_points_list': dropoff_points_list,
            'bins_summary_text': bins_summary_text,
            'bin_line_count': bin_line_count,
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
        user = request.env.user

        if not user.has_group(self.AGENT_GROUP):
            return request.redirect('/my/waste/requests?msg=no_worksheet_access')

        Worksheet = request.env['waste.worksheet'].sudo()
        ws = Worksheet.browse(worksheet_id)
        if not ws.exists():
            return request.not_found()

        # 🔹 load units of measure (you can filter if you want)
        Uom = request.env['uom.uom'].sudo()
        uoms = Uom.search([])

        # ----------------------------
        # Extra info from Manifest (Service Request)
        # ----------------------------
        req = ws.service_request_id.sudo()

        def _fmt_dt(dt):
            if not dt:
                return ""
            local_dt = fields.Datetime.context_timestamp(request.env.user, dt)
            return local_dt.strftime("%Y-%m-%d %H:%M")

        planned_date = _fmt_dt(
            getattr(req, "planned_date", False) or getattr(req, "service_request_date", False) or getattr(req,
                                                                                                          "create_date",
                                                                                                          False))

        # Pickup points (support both pickup_point_id and pickup_point_ids)
        pickup_points = []
        if req and 'pickup_point_id' in req._fields and req.pickup_point_id:
            pickup_points = [req.pickup_point_id]
        elif req and 'pickup_point_ids' in req._fields and req.pickup_point_ids:
            pickup_points = req.pickup_point_ids

        # Dropoff points (support dropoff_point_id / dropoff_point_ids)
        dropoff_points = []
        if req and 'dropoff_point_id' in req._fields and req.dropoff_point_id:
            dropoff_points = [req.dropoff_point_id]
        elif req and 'dropoff_point_ids' in req._fields and req.dropoff_point_ids:
            dropoff_points = req.dropoff_point_ids

        # Bin lifted / dropped (try common field names)
        bin_lifted = []
        for fname in ["bin_lifted_ids", "bins_lifted_ids", "lifted_bin_ids"]:
            if req and fname in req._fields and getattr(req, fname):
                bin_lifted = getattr(req, fname)
                break

        bin_dropped = []
        for fname in ["bin_dropped_ids", "bins_dropped_ids", "dropped_bin_ids", "bin_dripped_ids"]:
            if req and fname in req._fields and getattr(req, fname):
                bin_dropped = getattr(req, fname)
                break

        # Worksheet qty (product_uom_qty lives on worksheet in your POST save)
        product_uom_qty = getattr(ws, "product_uom_qty", 0.0) or 0.0

        values = {
            'page_name': 'waste_worksheet_edit',
            'worksheet': ws,
            'wsr': ws.service_request_id,
            'csrf_token': request.csrf_token(),
            'portal_msg': kw.get('msg'),  # ✅ add this line
            'uoms': uoms,          # ✅ add this
            'planned_date': planned_date,
            'pickup_points': pickup_points,
            'dropoff_points': dropoff_points,
            'bin_lifted': bin_lifted,
            'bin_dropped': bin_dropped,
            'product_uom_qty': product_uom_qty,

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
        user = request.env.user

        # Only agents may edit worksheets
        if not user.has_group(self.AGENT_GROUP):
            return request.redirect('/my/waste/requests?msg=no_worksheet_access')

        Worksheet = request.env['waste.worksheet'].sudo()
        ws = Worksheet.browse(worksheet_id)
        if not ws.exists():
            return request.not_found()

        def _convert_dt(val):
            if not val:
                return False
            val = val.replace('T', ' ')
            if len(val) == 16:
                val = val + ':00'
            return val

        vals = {}

        # ---------------- BASIC FIELDS ----------------
        arrival_raw = post.get('arrival_time')
        return_raw = post.get('return_date')

        if arrival_raw:
            vals['arrival_time'] = _convert_dt(arrival_raw)
        if return_raw:
            vals['return_date'] = _convert_dt(return_raw)

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

        # Billing quantity (updates SO line via write() on model)
        if post.get('product_uom_qty'):
            try:
                vals['product_uom_qty'] = float(post.get('product_uom_qty'))
            except Exception:
                pass

        if post.get('unit_of_measure'):
            try:
                vals['unit_of_measure'] = int(post.get('unit_of_measure'))
            except Exception:
                pass

        if post.get('notes_html'):
            vals['notes_html'] = post.get('notes_html')

        # ---------------- DOCS + SIGNATURES ----------------
        files = request.httprequest.files

        # Documents
        manifest = files.get('manifest_document')
        if manifest and manifest.filename:
            vals['manifest_document'] = base64.b64encode(manifest.read())
            vals['manifest_document_filename'] = manifest.filename

        weighbridge = files.get('weighbridge_slip')
        if weighbridge and weighbridge.filename:
            vals['weighbridge_slip'] = base64.b64encode(weighbridge.read())
            vals['weighbridge_slip_filename'] = weighbridge.filename

        safety = files.get('safety_certificate')
        if safety and safety.filename:
            vals['safety_certificate'] = base64.b64encode(safety.read())
            vals['safety_certificate_filename'] = safety.filename

        # SignaturePad data (driver & customer)
        # driver_sig_data = post.get('driver_signature_data')
        # if driver_sig_data and driver_sig_data.startswith('data:image'):
        #     try:
        #         vals['driver_signature'] = base64.b64decode(
        #             driver_sig_data.split(',', 1)[1]
        #         )
        #     except Exception:
        #         pass
        #
        # sp_sig_data = post.get('service_provider_signature_data')
        # if sp_sig_data and sp_sig_data.startswith('data:image'):
        #     try:
        #         vals['service_provider_signature'] = base64.b64decode(
        #             sp_sig_data.split(',', 1)[1]
        #         )
        #     except Exception:
        #         pass

        # SignaturePad data (driver & customer)
        driver_sig_data = post.get('driver_signature_data')
        if driver_sig_data and driver_sig_data.startswith('data:image'):
            # Odoo Binary fields expect base64-encoded data, NOT decoded bytes.
            # So we store just the base64 chunk after the comma.
            vals['driver_signature'] = driver_sig_data.split(',', 1)[1]

        sp_sig_data = post.get('service_provider_signature_data')
        if sp_sig_data and sp_sig_data.startswith('data:image'):
            vals['service_provider_signature'] = sp_sig_data.split(',', 1)[1]

        # ✅ WRITE EVERYTHING (including signatures) IN ONE GO
        if vals:
            ws.write(vals)

        # ============================================================
        # ✅ AFTER SAVE: update states
        # ============================================================
        ws_sudo = ws.sudo()

        # 1) Worksheet state -> done
        worksheet_became_done = False
        if 'state' in ws_sudo._fields and ws_sudo.state in ('in_progress', 'progress', 'ongoing'):
            ws_sudo.write({'state': 'done'})
            worksheet_became_done = True

        # 2) Manifest state: dispatched -> service_delivered
        req = ws_sudo.service_request_id.sudo()
        manifest_became_delivered = False
        if req and req.exists() and 'state' in req._fields and req.state == 'dispatched':
            req.write({'state': 'service_delivered'})
            manifest_became_delivered = True

        # ============================================================
        # ✅ SEND EMAIL: mail_tmpl_service_request_worksheet_completion
        # ============================================================
        # (send only when state changed, to avoid duplicate emails)
        if worksheet_became_done or manifest_became_delivered:
            tmpl = request.env.ref(
                'waste_management_zakheni.mail_tmpl_service_request_worksheet_completion',
                raise_if_not_found=False
            )
            if tmpl:
                # safest: send to the record that matches the template's model
                model = (tmpl.model_id.model if tmpl.model_id else '')
                if model == 'waste.service.request' and req:
                    tmpl.sudo().send_mail(req.id, force_send=True, raise_exception=False)
                elif model == 'waste.worksheet':
                    tmpl.sudo().send_mail(ws_sudo.id, force_send=True, raise_exception=False)
                else:
                    # fallback (most common is manifest)
                    if req:
                        tmpl.sudo().send_mail(req.id, force_send=True, raise_exception=False)

        # ---------------- PHOTOS: EDIT + REMOVE + ADD ----------------
        Image = request.env['waste.worksheet.image'].sudo()

        # 1) Edit existing photos (replace image + rename)
        for img in ws.image_ids:
            field_name = 'edit_image_%s' % img.id
            file_obj = request.httprequest.files.get(field_name)
            if file_obj and file_obj.filename:
                img.image = base64.b64encode(file_obj.read())

            name_field = 'edit_image_name_%s' % img.id
            new_name = post.get(name_field)
            if new_name is not None:
                img.name = new_name.strip() or img.name

        # 2) Remove checked photos
        remove_ids_str = request.httprequest.form.getlist('remove_image_ids')
        if remove_ids_str:
            remove_ids = [int(x) for x in remove_ids_str if x]
            imgs_to_remove = Image.browse(remove_ids).filtered(
                lambda i: i.worksheet_id.id == ws.id
            )
            if imgs_to_remove:
                imgs_to_remove.unlink()

        # 3) Add new photos
        new_files = request.httprequest.files.getlist('new_images')
        for img_file in new_files:
            if not img_file or not img_file.filename:
                continue
            Image.create({
                'worksheet_id': ws.id,
                'name': img_file.filename,
                'image': base64.b64encode(img_file.read()),
            })

        # ---------------- REDIRECT WITH SUCCESS MESSAGE + EMAIL ----------------

        # SEND EMAIL WHEN WORKSHEET IS UPDATED (PORTAL SIDE)
        template_agent = request.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_portal_worksheet_completion',
            raise_if_not_found=False,
        )
        if template_agent:
            # model of this template should be 'waste.worksheet'
            template_agent.sudo().send_mail(ws.id, force_send=True)

        # ---------------- REDIRECT WITH SUCCESS MESSAGE ----------------
        return request.redirect(
            '/my/waste/worksheet/%s/edit?msg=worksheet_saved' % ws.id
        )

    # ------------------------------------------------------------
    # DASHBOARD: /my/waste
    # ------------------------------------------------------------
    AGENT_GROUP = 'waste_management_zakheni.group_wmz_client_agent'

    @http.route(['/my/waste'], type='http', auth='user', website=True)
    def portal_waste_dashboard(self, **kw):
        user = request.env.user

        # Force SA timezone for portal rendering (only for this request env usage)
        env = request.env(context=dict(request.env.context, tz='Africa/Johannesburg'))

        WasteRequest = env['waste.service.request'].sudo()
        Worksheet = env['waste.worksheet'].sudo()
        AccountMove = env['account.move'].sudo()
        SaleOrder = env['sale.order'].sudo()

        is_agent = user.has_group(self.AGENT_GROUP)
        commercial_id = user.partner_id.commercial_partner_id.id

        # ---- base domain for requests ----
        if is_agent:
            base_domain = [
                ('partner_id', 'child_of', commercial_id),
                ('state', 'in', ['scheduled', 'dispatched', 'service_delivered', 'cancelled', 'done']),
            ]
        else:
            base_domain = [
                ('partner_id.commercial_partner_id', '=', commercial_id),
            ]

        closed_states = ['cancelled', 'done']

        total_requests = WasteRequest.search_count(base_domain)
        open_requests = WasteRequest.search_count(base_domain + [('state', 'not in', closed_states)])
        scheduled_requests = WasteRequest.search_count(base_domain + [('state', '=', 'scheduled')])
        dispatched_requests = WasteRequest.search_count(base_domain + [('state', '=', 'dispatched')])
        delivered_requests = WasteRequest.search_count(base_domain + [('state', '=', 'service_delivered')])
        done_requests = WasteRequest.search_count(base_domain + [('state', '=', 'done')])
        cancelled_requests = WasteRequest.search_count(base_domain + [('state', '=', 'cancelled')])

        # ---------- CHART DATA (from worksheets) ----------
        visible_requests = WasteRequest.search(base_domain)
        ws_domain = [('service_request_id', 'in', visible_requests.ids)]
        worksheets = Worksheet.search(ws_domain)

        def _manifest_bin_qty(req):
            """Return number of bins on this manifest (service request)."""
            if not req:
                return 0.0

            # Best: stored count on manifest
            if 'bin_line_count' in req._fields:
                return float(req.bin_line_count or 0.0)

            # Common: bin lines on manifest
            if 'bin_line_ids' in req._fields and req.bin_line_ids:
                lines = req.bin_line_ids
                if 'quantity' in lines._fields:
                    return float(sum(lines.mapped('quantity')) or 0.0)
                if 'qty' in lines._fields:
                    return float(sum(lines.mapped('qty')) or 0.0)
                return float(len(lines))

            # Common: direct bin many2many/one2many
            if 'bin_ids' in req._fields and req.bin_ids:
                return float(len(req.bin_ids))

            # Fallback: try lifted bins if that’s what you store on the manifest
            if 'bin_lifted_ids' in req._fields and req.bin_lifted_ids:
                return float(len(req.bin_lifted_ids))

            return 0.0

        revenue_by_customer = {}
        bins_by_customer = {}

        for ws in worksheets:
            req = ws.service_request_id
            if not req:
                continue

            # ✅ customer should come from the manifest to avoid wrong grouping
            cust = req.partner_id.commercial_partner_id or req.partner_id
            cust_name = cust.display_name or _("Unknown")

            revenue = getattr(ws, 'billing_amount', 0.0) or 0.0

            # ✅ bin qty comes from manifest (service request)
            bin_qty = _manifest_bin_qty(req)

            revenue_by_customer[cust_name] = revenue_by_customer.get(cust_name, 0.0) + revenue
            bins_by_customer[cust_name] = bins_by_customer.get(cust_name, 0.0) + bin_qty

        labels = list(revenue_by_customer.keys())
        revenue_data = [revenue_by_customer[l] for l in labels]
        bins_data = [bins_by_customer.get(l, 0.0) for l in labels]

        # ---------- DRIVER TRIPS LIST ----------
        driver_trips = Worksheet.search(ws_domain, order="arrival_time desc, create_date desc", limit=20)

        def _fmt_dt(dt):
            """Convert UTC datetime to Africa/Johannesburg and format."""
            if not dt:
                return ""
            local_dt = fields.Datetime.context_timestamp(user, dt)
            return local_dt.strftime("%Y-%m-%d %H:%M")

        def _manifest_planned_dt(req):
            dt = (getattr(req, 'planned_date', False)
                  or getattr(req, 'service_request_date', False)
                  or req.create_date)
            return _fmt_dt(dt)

        def _so_qty_for_manifest(req):
            """Sum product_uom_qty from all SO lines linked to this manifest (service_request_id)."""
            if not req:
                return 0.0

            so = False
            if 'sale_order_id' in req._fields and req.sale_order_id:
                so = req.sale_order_id
            else:
                so = SaleOrder.search([('service_request_id', '=', req.id)], limit=1)

            if not so:
                return 0.0

            return float(sum(so.order_line.mapped('product_uom_qty')) or 0.0)

        driver_trips_rows = []
        for trip in driver_trips:
            req = trip.service_request_id
            #
            # who = ""
            # if req and getattr(req, "is_service_provider", False) and getattr(req, "provider_id", False):
            #     who = req.provider_id.display_name or req.provider_id.name
            # elif getattr(trip, "driver_id", False):
            #     who = trip.driver_id.display_name or trip.driver_id.name
            # elif req and getattr(req, "driver_id", False):
            #     who = req.driver_id.display_name

            who = ""
            if req and getattr(req, "vehicle_id", False) and req.vehicle_id.driver_id:
                who = req.vehicle_id.driver_id.display_name
            elif req and getattr(req, "driver_id", False):
                who = req.driver_id.display_name
            elif getattr(trip, "driver_id", False):
                who = trip.driver_id.display_name

            qty_val = _so_qty_for_manifest(req)
            if not qty_val:
                qty_val = getattr(trip, "quantity_collected", 0.0) or 0.0

            driver_trips_rows.append({
                "arrival": _fmt_dt(trip.arrival_time or trip.create_date),
                "return": _fmt_dt(getattr(trip, "return_date", False)),
                "planned": _manifest_planned_dt(req) if req else "",
                "who": who or "-",
                "request": req.name if req else "-",
                "qty": qty_val,
                "revenue": getattr(trip, "billing_amount", 0.0) or 0.0,
            })

        # ============================================================
        # CLIENT REPORT (Manifest / Sales Order / Invoice / Total)
        # ============================================================
        date_from = (kw.get('date_from') or '').strip()
        date_to = (kw.get('date_to') or '').strip()
        manifest_no = (kw.get('manifest_no') or '').strip()
        sale_order_no = (kw.get('sale_order_no') or '').strip()
        invoice_no = (kw.get('invoice_no') or '').strip()

        manifest_domain = list(base_domain)

        if manifest_no:
            manifest_domain += [('name', 'ilike', manifest_no)]

        if date_from:
            if 'planned_date' in WasteRequest._fields:
                manifest_domain += [('planned_date', '>=', date_from)]
            else:
                manifest_domain += [('service_request_date', '>=', date_from)]

        if date_to:
            if 'planned_date' in WasteRequest._fields:
                manifest_domain += [('planned_date', '<=', date_to)]
            else:
                manifest_domain += [('service_request_date', '<=', date_to)]

        manifest_ids_restrict = None

        if sale_order_no:
            so_restrict_domain = [('state', '!=', 'cancel'), ('name', 'ilike', sale_order_no)]
            if is_agent:
                so_restrict_domain += [('partner_id', 'child_of', commercial_id)]
            else:
                so_restrict_domain += [('partner_id.commercial_partner_id', '=', commercial_id)]
            so_hits = SaleOrder.search(so_restrict_domain)
            manifest_ids_restrict = set(so_hits.mapped('service_request_id').ids)

        if invoice_no:
            inv_restrict_domain = [
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', '!=', 'cancel'),
                ('name', 'ilike', invoice_no),
            ]
            if is_agent:
                inv_restrict_domain += [('partner_id', 'child_of', commercial_id)]
            else:
                inv_restrict_domain += [('partner_id.commercial_partner_id', '=', commercial_id)]

            inv_hits = AccountMove.search(inv_restrict_domain)

            so_from_lines = inv_hits.invoice_line_ids.sale_line_ids.order_id
            origins = [o for o in inv_hits.mapped('invoice_origin') if o]
            so_from_origin = SaleOrder.search([('name', 'in', origins)]) if origins else SaleOrder.browse()

            so_all = (so_from_lines | so_from_origin)
            if sale_order_no:
                so_all = so_all.filtered(lambda s: sale_order_no.lower() in (s.name or '').lower())

            inv_manifest_ids = set(so_all.mapped('service_request_id').ids)
            manifest_ids_restrict = inv_manifest_ids if manifest_ids_restrict is None \
                else manifest_ids_restrict.intersection(inv_manifest_ids)

        if manifest_ids_restrict is not None:
            if not manifest_ids_restrict:
                manifests = WasteRequest.browse()
            else:
                manifest_domain += [('id', 'in', list(manifest_ids_restrict))]
                manifests = WasteRequest.search(manifest_domain, order="create_date desc")
        else:
            manifests = WasteRequest.search(manifest_domain, order="create_date desc")

        report_rows = []
        if manifests:
            so_domain = [('service_request_id', 'in', manifests.ids), ('state', '!=', 'cancel')]
            if sale_order_no:
                so_domain += [('name', 'ilike', sale_order_no)]
            sale_orders = SaleOrder.search(so_domain)

            so_by_manifest = {}
            for so in sale_orders:
                so_by_manifest.setdefault(so.service_request_id.id, []).append(so)

            so_ids = sale_orders.ids
            so_names = sale_orders.mapped('name')

            inv_domain = [
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', '!=', 'cancel'),
            ]
            if is_agent:
                inv_domain += [('partner_id', 'child_of', commercial_id)]
            else:
                inv_domain += [('partner_id.commercial_partner_id', '=', commercial_id)]
            if invoice_no:
                inv_domain += [('name', 'ilike', invoice_no)]

            invoices = AccountMove.browse()
            if so_names or so_ids:
                inv_domain += ['|',
                               ('invoice_origin', 'in', so_names),
                               ('invoice_line_ids.sale_line_ids.order_id', 'in', so_ids)]
                invoices = AccountMove.search(inv_domain, order="invoice_date desc, id desc")

            inv_by_origin = {}
            inv_by_so_id = {}
            for inv in invoices:
                if inv.invoice_origin:
                    inv_by_origin.setdefault(inv.invoice_origin, []).append(inv)
                for so in inv.invoice_line_ids.sale_line_ids.order_id:
                    inv_by_so_id.setdefault(so.id, []).append(inv)

            for manifest in manifests:
                planned_dt = _manifest_planned_dt(manifest)
                m_sos = so_by_manifest.get(manifest.id, [])

                if not m_sos:
                    report_rows.append({
                        'planned_date': planned_dt,
                        'manifest': manifest,
                        'sale_order': False,
                        'invoice': False,
                        'total': 0.0,
                    })
                    continue

                for so in m_sos:
                    invs = (inv_by_origin.get(so.name, []) + inv_by_so_id.get(so.id, []))
                    if invs:
                        invs = list({i.id: i for i in invs}.values())

                    if not invs:
                        report_rows.append({
                            'planned_date': planned_dt,
                            'manifest': manifest,
                            'sale_order': so,
                            'invoice': False,
                            'total': 0.0,
                        })
                        continue

                    for inv in invs:
                        report_rows.append({
                            'planned_date': planned_dt,
                            'manifest': manifest,
                            'sale_order': so,
                            'invoice': inv,
                            'total': inv.amount_total or 0.0,
                        })

        # -----------------------------
        # PAGINATION (Client Report + Driver Trips) - ONCE
        # -----------------------------
        report_page = int(kw.get('report_page') or 1)
        report_page_size = 20
        report_total = len(report_rows)
        report_pager = portal_pager(
            url="/my/waste",
            total=report_total,
            page=report_page,
            step=report_page_size,
            scope=5,
            url_args=dict(kw),
        )
        report_rows_page = report_rows[(report_page - 1) * report_page_size: report_page * report_page_size]

        trips_page = int(kw.get('trips_page') or 1)
        trips_page_size = 20
        trips_total = len(driver_trips_rows)
        trips_pager = portal_pager(
            url="/my/waste",
            total=trips_total,
            page=trips_page,
            step=trips_page_size,
            scope=5,
            url_args=dict(kw),
        )
        driver_trips_rows_page = driver_trips_rows[(trips_page - 1) * trips_page_size: trips_page * trips_page_size]

        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'waste_dashboard',
            'is_agent': is_agent,

            'total_requests': total_requests,
            'open_requests': open_requests,
            'scheduled_requests': scheduled_requests,
            'dispatched_requests': dispatched_requests,
            'delivered_requests': delivered_requests,
            'done_requests': done_requests,
            'cancelled_requests': cancelled_requests,

            'chart_labels_json': json.dumps(labels),
            'chart_revenue_json': json.dumps(revenue_data),
            'chart_bins_json': json.dumps(bins_data),

            'driver_trips': driver_trips,
            'driver_trips_rows': driver_trips_rows,

            # Client Report pager + page rows
            'report_pager': report_pager,
            'report_rows_page': report_rows_page,
            'report_total': report_total,

            # Driver Trips pager + page rows
            'trips_pager': trips_pager,
            'driver_trips_rows_page': driver_trips_rows_page,
            'trips_total': trips_total,

            'report_filters': {
                'date_from': date_from,
                'date_to': date_to,
                'manifest_no': manifest_no,
                'sale_order_no': sale_order_no,
                'invoice_no': invoice_no,
            },
            'report_rows': report_rows,
        })

        return request.render('waste_management_zakheni.portal_waste_dashboard', values)

    def _get_allowed_client_ids(self, user):
        """Partners the user is allowed to see (company + contacts)."""
        commercial = user.partner_id.commercial_partner_id
        allowed = request.env['res.partner'].sudo().search([('id', 'child_of', commercial.id)])
        return allowed.ids

    @http.route(['/my/waste/report'], type='http', auth='user', website=True)
    def portal_waste_print_report(self, **kw):
        user = request.env.user
        env = request.env(context=dict(request.env.context, tz='Africa/Johannesburg'))

        WasteRequest = env['waste.service.request'].sudo()
        Worksheet = env['waste.worksheet'].sudo()
        SaleOrder = env['sale.order'].sudo()
        AccountMove = env['account.move'].sudo()

        commercial_id = user.partner_id.commercial_partner_id.id
        is_agent = user.has_group(self.AGENT_GROUP)

        filters = {
            'date_from': (kw.get('date_from') or '').strip(),
            'date_to': (kw.get('date_to') or '').strip(),
            'manifest_no': (kw.get('manifest_no') or '').strip(),
            'sale_order_no': (kw.get('sale_order_no') or '').strip(),
            'invoice_no': (kw.get('invoice_no') or '').strip(),
        }

        # -------------------------
        # Base domain (same as dashboard)
        # -------------------------
        if is_agent:
            base_domain = [
                ('partner_id', 'child_of', commercial_id),
                ('state', 'in', ['scheduled', 'dispatched', 'service_delivered', 'cancelled', 'done']),
            ]
        else:
            base_domain = [
                ('partner_id.commercial_partner_id', '=', commercial_id),
            ]

        # -------------------------
        # Helpers
        # -------------------------
        def _fmt_dt(dt):
            if not dt:
                return ""
            local_dt = fields.Datetime.context_timestamp(user, dt)
            return local_dt.strftime("%Y-%m-%d %H:%M")

        def _manifest_planned_dt(req):
            dt = (getattr(req, 'planned_date', False)
                  or getattr(req, 'service_request_date', False)
                  or req.create_date)
            return _fmt_dt(dt)

        # ============================================================
        #  A) CLIENT REPORT rows (your working logic)
        # ============================================================
        manifest_domain = list(base_domain)

        if filters['manifest_no']:
            manifest_domain += [('name', 'ilike', filters['manifest_no'])]

        if filters['date_from']:
            if 'planned_date' in WasteRequest._fields:
                manifest_domain += [('planned_date', '>=', filters['date_from'])]
            else:
                manifest_domain += [('service_request_date', '>=', filters['date_from'])]

        if filters['date_to']:
            if 'planned_date' in WasteRequest._fields:
                manifest_domain += [('planned_date', '<=', filters['date_to'])]
            else:
                manifest_domain += [('service_request_date', '<=', filters['date_to'])]

        manifests = WasteRequest.search(manifest_domain, order="create_date desc")

        rows = []
        if manifests:
            so_domain = [('service_request_id', 'in', manifests.ids), ('state', '!=', 'cancel')]
            if filters['sale_order_no']:
                so_domain += [('name', 'ilike', filters['sale_order_no'])]
            sale_orders = SaleOrder.search(so_domain)

            so_by_manifest = {}
            for so in sale_orders:
                so_by_manifest.setdefault(so.service_request_id.id, []).append(so)

            so_ids = sale_orders.ids
            so_names = sale_orders.mapped('name')

            invoices = AccountMove.browse()
            if so_names or so_ids:
                inv_domain = [
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('state', '!=', 'cancel'),
                ]
                if is_agent:
                    inv_domain += [('partner_id', 'child_of', commercial_id)]
                else:
                    inv_domain += [('partner_id.commercial_partner_id', '=', commercial_id)]

                if filters['invoice_no']:
                    inv_domain += [('name', 'ilike', filters['invoice_no'])]

                inv_domain += ['|',
                               ('invoice_origin', 'in', so_names),
                               ('invoice_line_ids.sale_line_ids.order_id', 'in', so_ids)]
                invoices = AccountMove.search(inv_domain, order="invoice_date desc, id desc")

            inv_by_origin = {}
            inv_by_so_id = {}
            for inv in invoices:
                if inv.invoice_origin:
                    inv_by_origin.setdefault(inv.invoice_origin, []).append(inv)
                for so in inv.invoice_line_ids.sale_line_ids.order_id:
                    inv_by_so_id.setdefault(so.id, []).append(inv)

            for manifest in manifests:
                planned_dt = _manifest_planned_dt(manifest)
                m_sos = so_by_manifest.get(manifest.id, [])

                if not m_sos:
                    rows.append({
                        'planned_date': planned_dt,
                        'manifest': manifest.name or '',
                        'sale_order': '',
                        'invoice': '',
                        'total': 0.0,
                    })
                    continue

                for so in m_sos:
                    invs = (inv_by_origin.get(so.name, []) + inv_by_so_id.get(so.id, []))
                    if invs:
                        invs = list({i.id: i for i in invs}.values())

                    if not invs:
                        rows.append({
                            'planned_date': planned_dt,
                            'manifest': manifest.name or '',
                            'sale_order': so.name or '',
                            'invoice': '',
                            'total': 0.0,
                        })
                        continue

                    for inv in invs:
                        rows.append({
                            'planned_date': planned_dt,
                            'manifest': manifest.name or '',
                            'sale_order': so.name or '',
                            'invoice': inv.name or '',
                            'total': float(inv.amount_total or 0.0),
                        })

        # ============================================================
        #  B) SERVICE REQUESTS SUMMARY
        # ============================================================
        requests_summary = WasteRequest.search(base_domain, order="create_date desc", limit=50)

        requests_summary_rows = []
        for req in requests_summary:
            requests_summary_rows.append({
                'name': req.name or '',
                'date': _fmt_dt(req.create_date or req.service_request_date),
                'state': req.state or '',
                'customer': (req.partner_id.display_name or ''),
            })

        # ============================================================
        #  C) RECENT DRIVER TRIPS (worksheets)
        # ============================================================
        ws_domain = [('service_request_id', 'in', requests_summary.ids)]
        recent_trips = Worksheet.search(ws_domain, order="arrival_time desc, create_date desc", limit=20)

        recent_trips_rows = []
        for ws in recent_trips:
            req = ws.service_request_id
            who = ''
            if ws.driver_id:
                who = ws.driver_id.display_name or ''
            elif req and getattr(req, "driver_id", False):
                who = req.driver_id.display_name or ''

            recent_trips_rows.append({
                'arrival': _fmt_dt(ws.arrival_time or ws.create_date),
                'return': _fmt_dt(getattr(ws, "return_date", False)),
                'planned': _manifest_planned_dt(req) if req else '',
                'manifest': req.name if req else '',
                'driver': who,
                'qty': float(getattr(ws, "product_uom_qty", 0.0) or ws.quantity_collected or 0.0),
                'revenue': float(getattr(ws, "billing_amount", 0.0) or 0.0),
            })

        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'waste_report',
            'user': user,
            'filters': filters,

            # Client Report
            'rows': rows,

            # New tables for HTML page
            'requests_summary_rows': requests_summary_rows,
            'recent_trips_rows': recent_trips_rows,
        })
        return request.render('waste_management_zakheni.portal_waste_report_html', values)

    @http.route(['/my/waste/report/pdf'], type='http', auth='user', website=True)
    def portal_waste_report_pdf(self, **kw):
        user = request.env.user
        env = request.env(context=dict(request.env.context, tz='Africa/Johannesburg'))

        WasteRequest = env['waste.service.request'].sudo()
        commercial_id = user.partner_id.commercial_partner_id.id

        # ✅ accept both naming styles (dashboard + html report)
        date_from = (kw.get('date_from') or '').strip()
        date_to = (kw.get('date_to') or '').strip()

        manifest_no = (kw.get('manifest_no') or kw.get('manifest') or '').strip()
        sale_order_no = (kw.get('sale_order_no') or kw.get('sale_order') or '').strip()
        invoice_no = (kw.get('invoice_no') or kw.get('invoice') or '').strip()

        # ✅ SAME base domain as dashboard
        manifest_domain = [('partner_id.commercial_partner_id', '=', commercial_id)]

        if manifest_no:
            manifest_domain += [('name', 'ilike', manifest_no)]

        if date_from:
            if 'planned_date' in WasteRequest._fields:
                manifest_domain += [('planned_date', '>=', date_from)]
            else:
                manifest_domain += [('service_request_date', '>=', date_from + ' 00:00:00')]

        if date_to:
            if 'planned_date' in WasteRequest._fields:
                manifest_domain += [('planned_date', '<=', date_to)]
            else:
                manifest_domain += [('service_request_date', '<=', date_to + ' 23:59:59')]

        manifests = WasteRequest.search(manifest_domain, order="create_date desc")
        if not manifests:
            return request.redirect('/my/waste?msg=no_records')

        data = {
            'filters': {
                'date_from': date_from,
                'date_to': date_to,
                'manifest_no': manifest_no,
                'sale_order_no': sale_order_no,
                'invoice_no': invoice_no,
            }
        }

        report_xmlid = 'waste_management_zakheni.action_portal_waste_pdf'

        pdf_content, content_type = env['ir.actions.report']._render_qweb_pdf(
            report_xmlid, manifests.ids, data=data
        )

        filename = "waste_service_report.pdf"
        headers = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', f'attachment; filename="{filename}"'),
        ]
        return request.make_response(pdf_content, headers)

    @http.route(['/my/waste/report/xlsx'], type='http', auth='user', website=True)
    def portal_waste_report_xlsx(self, **kw):
        import io
        import xlsxwriter

        user = request.env.user
        env = request.env(context=dict(request.env.context, tz='Africa/Johannesburg'))

        WasteRequest = env['waste.service.request'].sudo()
        Worksheet = env['waste.worksheet'].sudo()

        SaleOrder = env['sale.order'].sudo()
        AccountMove = env['account.move'].sudo()

        commercial_id = user.partner_id.commercial_partner_id.id
        base_domain = [('partner_id.commercial_partner_id', '=', commercial_id)]

        # Requests (for sheets 2/3)
        # requests = WasteRequest.search(base_domain)
        requests = WasteRequest.search([('partner_id', 'child_of', commercial_id)])
        worksheets = Worksheet.search([('service_request_id', 'in', requests.ids)])

        # Filters (same naming as dashboard)
        filters = {
            'date_from': (kw.get('date_from') or '').strip(),
            'date_to': (kw.get('date_to') or '').strip(),
            'manifest_no': (kw.get('manifest_no') or '').strip(),
            'sale_order_no': (kw.get('sale_order_no') or '').strip(),
            'invoice_no': (kw.get('invoice_no') or '').strip(),
        }

        # ---- Build client rows (same logic as report) ----
        # If you want: import your report helper instead of duplicating.
        # For now, quick inline reuse with same logic approach:
        def _fmt_dt(dt):
            if not dt:
                return ""
            local_dt = fields.Datetime.context_timestamp(user, dt)
            return local_dt.strftime("%Y-%m-%d %H:%M")

        def _manifest_planned_dt(req):
            dt = (getattr(req, 'planned_date', False)
                  or getattr(req, 'service_request_date', False)
                  or req.create_date)
            return _fmt_dt(dt)

        manifest_domain = list(base_domain)
        if filters['manifest_no']:
            manifest_domain += [('name', 'ilike', filters['manifest_no'])]

        if filters['date_from']:
            if 'planned_date' in WasteRequest._fields:
                manifest_domain += [('planned_date', '>=', filters['date_from'])]
            else:
                manifest_domain += [('service_request_date', '>=', filters['date_from'])]

        if filters['date_to']:
            if 'planned_date' in WasteRequest._fields:
                manifest_domain += [('planned_date', '<=', filters['date_to'])]
            else:
                manifest_domain += [('service_request_date', '<=', filters['date_to'])]

        manifests = WasteRequest.search(manifest_domain, order="create_date desc")

        report_rows = []
        if manifests:
            sale_orders = SaleOrder.search([('service_request_id', 'in', manifests.ids), ('state', '!=', 'cancel')])
            if filters['sale_order_no']:
                sale_orders = sale_orders.filtered(lambda s: filters['sale_order_no'].lower() in (s.name or '').lower())

            so_by_manifest = {}
            for so in sale_orders:
                so_by_manifest.setdefault(so.service_request_id.id, []).append(so)

            so_ids = sale_orders.ids
            so_names = sale_orders.mapped('name')

            invoices = AccountMove.browse()
            if so_names or so_ids:
                inv_domain = [
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('state', '!=', 'cancel'),
                    '|',
                    ('invoice_origin', 'in', so_names),
                    ('invoice_line_ids.sale_line_ids.order_id', 'in', so_ids),
                ]
                if filters['invoice_no']:
                    inv_domain += [('name', 'ilike', filters['invoice_no'])]
                invoices = AccountMove.search(inv_domain, order="invoice_date desc, id desc")

            inv_by_origin = {}
            inv_by_so_id = {}
            for inv in invoices:
                if inv.invoice_origin:
                    inv_by_origin.setdefault(inv.invoice_origin, []).append(inv)
                for so in inv.invoice_line_ids.sale_line_ids.order_id:
                    inv_by_so_id.setdefault(so.id, []).append(inv)

            for manifest in manifests:
                planned_dt = _manifest_planned_dt(manifest)
                m_sos = so_by_manifest.get(manifest.id, [])

                if not m_sos:
                    report_rows.append([planned_dt, manifest.name, "", "", 0.0])
                    continue

                for so in m_sos:
                    invs = (inv_by_origin.get(so.name, []) + inv_by_so_id.get(so.id, []))
                    if invs:
                        invs = list({i.id: i for i in invs}.values())

                    if not invs:
                        report_rows.append([planned_dt, manifest.name, so.name, "", 0.0])
                        continue

                    for inv in invs:
                        report_rows.append(
                            [planned_dt, manifest.name, so.name, inv.name, float(inv.amount_total or 0.0)])

        # Create in-memory file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        header_fmt = workbook.add_format({'bold': True})

        # Sheet 1: Client Report
        sh_client = workbook.add_worksheet("Client Report")
        headers_client = ["Planned Date", "Manifest", "Sales Order", "Invoice Number", "Total"]
        for col, h in enumerate(headers_client):
            sh_client.write(0, col, h, header_fmt)

        row = 1
        for r in report_rows:
            sh_client.write(row, 0, r[0])
            sh_client.write(row, 1, r[1])
            sh_client.write(row, 2, r[2])
            sh_client.write(row, 3, r[3])
            sh_client.write_number(row, 4, r[4] or 0.0)
            row += 1

        # Sheet 2: Requests
        sheet_req = workbook.add_worksheet("Requests")
        headers_req = ["Name", "Date", "Status", "Customer"]
        for col, h in enumerate(headers_req):
            sheet_req.write(0, col, h, header_fmt)

        row = 1
        for req in requests:
            sheet_req.write(row, 0, req.name or "")
            sheet_req.write(row, 1, str(req.create_date or ""))
            sheet_req.write(row, 2, req.state or "")
            sheet_req.write(row, 3, req.partner_id.display_name or "")
            row += 1

        # Sheet 3: Driver Trips
        sheet_ws = workbook.add_worksheet("Driver Trips")
        headers_ws = ["Date", "Driver", "Quantity", "Revenue"]
        for col, h in enumerate(headers_ws):
            sheet_ws.write(0, col, h, header_fmt)

        row = 1
        for ws in worksheets:
            sheet_ws.write(row, 0, str(ws.arrival_time or ws.create_date or ""))
            sheet_ws.write(row, 1, ws.driver_id.display_name if ws.driver_id else "")
            sheet_ws.write_number(row, 2, ws.quantity_collected or 0.0)
            sheet_ws.write_number(row, 3, getattr(ws, 'billing_amount', 0.0) or 0.0)
            row += 1

        workbook.close()
        output.seek(0)

        xlsx_data = output.read()
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Length', len(xlsx_data)),
            ('Content-Disposition', 'attachment; filename="waste_service_report.xlsx"'),
        ]
        return request.make_response(xlsx_data, headers)

    @http.route('/my/waste/pickup_points', type='json', auth='user', website=True)
    def portal_pickup_points_by_customer(self, partner_id=None, **kw):
        user = request.env.user
        commercial_id = user.partner_id.commercial_partner_id.id

        try:
            partner_id = int(partner_id or 0)
        except Exception:
            partner_id = 0

        # Security: only allow within same commercial group
        Partner = request.env['res.partner'].sudo()
        p = Partner.browse(partner_id)
        if not p or not p.exists() or p.commercial_partner_id.id != commercial_id:
            return []

        PickupPoint = request.env['pickup.point'].sudo()
        points = PickupPoint.search([('partner_id', '=', p.id)], order="name asc")

        return [{'id': pp.id, 'name': pp.display_name} for pp in points]

    @http.route(
        '/my/waste/pickup_points/create',
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
        csrf=False
    )
    def portal_pickup_points_create(self, **kw):
        # ✅ Read JSON body (fetch sends raw JSON, not Odoo jsonrpc)
        data = {}
        try:
            raw = request.httprequest.get_data(as_text=True)  # or .data
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {}

        # Fallback if someone posts form-data
        if not data:
            data = dict(request.params or {})

        # -------- validate inputs --------
        try:
            partner_id = int(data.get('partner_id') or 0)
        except Exception:
            partner_id = 0

        name = (data.get('name') or '').strip()

        if not partner_id or not name:
            return request.make_json_response({
                'error': _('Client and Address Name are required.')
            })

        # optional: security check (only allow within current user commercial group)
        user = request.env.user
        commercial_id = user.partner_id.commercial_partner_id.id

        Partner = request.env['res.partner'].sudo()
        p = Partner.browse(partner_id)
        if not p.exists():
            return request.make_json_response({'error': _('Invalid client selected.')})

        # ✅ IMPORTANT: allow only same commercial group
        if p.commercial_partner_id.id != commercial_id:
            return request.make_json_response({'error': _('Not allowed for this client.')})

        pp = request.env['pickup.point'].sudo().create({
            'name': name,
            'partner_id': p.id,
        })

        return request.make_json_response({'id': pp.id, 'name': pp.name})


    @http.route('/wmz/ping', type='http', auth='public', website=True)
    def wmz_ping(self, **kw):
        return "WMZ OK"
