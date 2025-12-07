# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import datetime


class ReportPortalWastePDF(models.AbstractModel):
    _name = "report.waste_management_zakheni.portal_waste_report_pdf"
    _description = "Portal Waste PDF Report"

    def _fmt_dt(self, user, dt):
        if not dt:
            return ""
        local_dt = fields.Datetime.context_timestamp(user, dt)
        return local_dt.strftime("%Y-%m-%d %H:%M")

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        user = self.env.user

        WasteRequest = self.env["waste.service.request"].sudo()
        Worksheet = self.env["waste.worksheet"].sudo()
        SaleOrder = self.env["sale.order"].sudo()
        AccountMove = self.env["account.move"].sudo()

        commercial_id = user.partner_id.commercial_partner_id.id

        # filters passed from controller
        client_filters = (data.get("filters") or {})
        date_from = (client_filters.get("date_from") or "").strip()
        date_to = (client_filters.get("date_to") or "").strip()
        manifest_no = (client_filters.get("manifest_no") or "").strip()
        sale_order_no = (client_filters.get("sale_order_no") or "").strip()
        invoice_no = (client_filters.get("invoice_no") or "").strip()

        # ---------------------------------------------------
        # MANIFESTS (docs) domain
        # ---------------------------------------------------
        manifest_domain = [('partner_id.commercial_partner_id', '=', commercial_id)]

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

        manifests = WasteRequest.search(manifest_domain, order="create_date desc")
        docs = manifests if manifests else WasteRequest.browse(docids)

        def _manifest_planned_dt(req):
            dt = (getattr(req, 'planned_date', False)
                  or getattr(req, 'service_request_date', False)
                  or req.create_date)
            return self._fmt_dt(user, dt)

        # ---------------------------------------------------
        # CLIENT ROWS (Planned | Manifest | SO | Invoice | Total)
        # ---------------------------------------------------
        client_rows = []
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

            invoices = AccountMove.browse()
            if so_names or so_ids:
                inv_domain = [
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('state', '!=', 'cancel'),
                    ('partner_id.commercial_partner_id', '=', commercial_id),
                    '|',
                    ('invoice_origin', 'in', so_names),
                    ('invoice_line_ids.sale_line_ids.order_id', 'in', so_ids),
                ]
                if invoice_no:
                    inv_domain += [('name', 'ilike', invoice_no)]
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
                    client_rows.append({
                        'planned_date': planned_dt,
                        'manifest': manifest.name,
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
                        client_rows.append({
                            'planned_date': planned_dt,
                            'manifest': manifest.name,
                            'sale_order': so.name,
                            'invoice': '',
                            'total': 0.0,
                        })
                        continue

                    for inv in invs:
                        client_rows.append({
                            'planned_date': planned_dt,
                            'manifest': manifest.name,
                            'sale_order': so.name,
                            'invoice': inv.name or '',
                            'total': float(inv.amount_total or 0.0),
                        })

        # ---------------------------------------------------
        # RECENT DRIVER TRIPS (worksheets)
        # ---------------------------------------------------
        ws_domain = [('service_request_id.partner_id.commercial_partner_id', '=', commercial_id)]
        if manifests:
            ws_domain += [('service_request_id', 'in', manifests.ids)]

        recent_ws = Worksheet.search(ws_domain, order="arrival_time desc, create_date desc", limit=20)

        recent_trips = []
        for ws in recent_ws:
            req = ws.service_request_id
            recent_trips.append({
                "arrival": self._fmt_dt(user, ws.arrival_time or ws.create_date),
                "return": self._fmt_dt(user, ws.return_date),
                "planned": _manifest_planned_dt(req) if req else "",
                "manifest": req.name if req else "",
                "driver": (ws.driver_id.display_name if ws.driver_id else ""),
                "qty": float(ws.product_uom_qty or ws.quantity_collected or 0.0),
                "revenue": float(getattr(ws, "billing_amount", 0.0) or 0.0),
            })

        return {
            "doc_ids": docs.ids,
            "doc_model": "waste.service.request",
            "docs": docs,

            "user": user,
            "client_filters": client_filters,
            "client_rows": client_rows,

            # ✅ for PDF section
            "recent_trips": recent_trips,
        }

