# -*- coding: utf-8 -*-
import io
import json
import urllib.parse
from odoo import http, fields
from odoo.http import request


class WasteDashboardExportController(http.Controller):

    def _safe_filters(self, filters):
        """Make sure partner_id/company_id are ints or False (ignore 'All Customers', etc)."""
        def _safe_int(v):
            if not v:
                return False
            if isinstance(v, (list, tuple)) and v:
                v = v[0]
            if isinstance(v, int):
                return v
            if isinstance(v, str):
                s = v.strip()
                return int(s) if s.isdigit() else False
            try:
                return int(v)
            except Exception:
                return False

        filters = filters or {}
        filters = dict(filters)

        filters["partner_id"] = _safe_int(filters.get("partner_id"))
        filters["company_id"] = _safe_int(filters.get("company_id"))
        return filters

    @http.route("/waste_dashboard/export_xlsx", type="http", auth="user")
    def export_dashboard_xlsx(self, filters=None, **kw):
        # 1) decode filters
        filters = filters or "{}"
        try:
            filters = urllib.parse.unquote(filters)
            filters = json.loads(filters) if isinstance(filters, str) else (filters or {})
        except Exception:
            filters = {}

        filters = self._safe_filters(filters)

        # 2) get SAME payload used by dashboard (so filters apply consistently)
        Request = request.env["waste.service.request"].sudo()
        payload = Request.get_dashboard_payload(filters)  # <- must accept dict filters

        # 3) build xlsx
        output = io.BytesIO()
        # workbook = request.env["ir.actions.report"]._get_report_base_filename("Waste_Dashboard")  # safe default name
        filename = "Waste_Dashboard.xlsx"

        import xlsxwriter
        wb = xlsxwriter.Workbook(output, {"in_memory": True})

        fmt_title = wb.add_format({"bold": True, "font_size": 14})
        fmt_head = wb.add_format({"bold": True, "bg_color": "#F2F2F2", "border": 1})
        fmt_cell = wb.add_format({"border": 1})
        fmt_money = wb.add_format({"border": 1, "num_format": "#,##0.00"})
        fmt_date = wb.add_format({"border": 1, "num_format": "yyyy-mm-dd"})

        # --- Sheet: Summary ---
        ws = wb.add_worksheet("Summary")
        ws.write(0, 0, "Waste Dashboard Export", fmt_title)
        ws.write(2, 0, "Printed at")
        ws.write(2, 1, fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ws.write(3, 0, "User")
        ws.write(3, 1, request.env.user.name)

        # Filters block
        ws.write(5, 0, "Filters", fmt_head)
        r = 6
        for k in ["date_from", "date_to", "manifest_number", "sale_order_number", "invoice_number", "company_id", "partner_id", "ticket_type"]:
            v = (filters or {}).get(k)
            if v:
                ws.write(r, 0, k, fmt_cell)
                ws.write(r, 1, str(v), fmt_cell)
                r += 1

        # KPIs
        kpis = payload.get("kpis") or {}
        ws.write(5, 3, "KPIs", fmt_head)
        kpi_rows = [
            ("Open Requests", kpis.get("open_requests", 0)),
            ("Scheduled", kpis.get("scheduled_count", 0)),
            ("In Progress", kpis.get("in_progress", 0)),
            ("Done", kpis.get("done_count", 0)),
            ("Rejected", kpis.get("rejected_count", 0)),
            ("Tank kL (Month)", kpis.get("tank_kl_month", 0)),
            ("Billing (Month)", kpis.get("billing_amount_month", 0)),
        ]
        rr = 6
        for label, val in kpi_rows:
            ws.write(rr, 3, label, fmt_cell)
            if "Billing" in label:
                ws.write_number(rr, 4, float(val or 0.0), fmt_money)
            else:
                ws.write_number(rr, 4, float(val or 0.0), fmt_cell)
            rr += 1

        ws.set_column(0, 0, 22)
        ws.set_column(1, 1, 35)
        ws.set_column(3, 3, 22)
        ws.set_column(4, 4, 18)

        # --- Sheet: Manifests (table) ---
        ws2 = wb.add_worksheet("Manifests")
        headers = ["Planned Date", "Manifest", "Customer", "Status", "Bins", "Sales Order", "Invoice", "Total"]
        for c, h in enumerate(headers):
            ws2.write(0, c, h, fmt_head)

        # Prefer the already prepared summary rows from payload
        # Adjust keys to your payload output (based on your previous code)
        manifest_rows = payload.get("manifest_summary") or payload.get("manifests") or []
        row = 1
        for x in manifest_rows:
            # try common keys you already use
            planned = x.get("date") or x.get("service_request_date") or x.get("planned_date") or ""
            ws2.write(row, 0, str(planned), fmt_cell)
            ws2.write(row, 1, x.get("manifest") or x.get("name") or "", fmt_cell)
            ws2.write(row, 2, x.get("customer") or x.get("partner") or "", fmt_cell)
            ws2.write(row, 3, x.get("status") or x.get("state") or "", fmt_cell)
            ws2.write_number(row, 4, float(x.get("bin_count") or x.get("bins") or 0), fmt_cell)
            ws2.write(row, 5, x.get("so") or x.get("sale_order") or "", fmt_cell)
            ws2.write(row, 6, x.get("invoice") or x.get("invoice_number") or "", fmt_cell)
            ws2.write_number(row, 7, float(x.get("total") or 0.0), fmt_money)
            row += 1

        ws2.set_column(0, 0, 14)
        ws2.set_column(1, 1, 18)
        ws2.set_column(2, 2, 30)
        ws2.set_column(3, 3, 14)
        ws2.set_column(4, 4, 8)
        ws2.set_column(5, 6, 18)
        ws2.set_column(7, 7, 14)

        # --- Sheet: SO-Invoice Totals ---
        ws3 = wb.add_worksheet("SO-Invoice Totals")
        headers = ["Manifest", "Sales Order", "Invoice", "Total"]
        for c, h in enumerate(headers):
            ws3.write(0, c, h, fmt_head)

        so_inv_rows = payload.get("so_invoice_totals") or payload.get("so_invoice_map") or []
        row = 1
        total_sum = 0.0
        for x in so_inv_rows:
            ws3.write(row, 0, x.get("manifest") or "", fmt_cell)
            ws3.write(row, 1, x.get("sale_order") or x.get("so") or "", fmt_cell)
            ws3.write(row, 2, x.get("invoice") or "", fmt_cell)
            amount = float(x.get("total") or 0.0)
            ws3.write_number(row, 3, amount, fmt_money)
            total_sum += amount
            row += 1

        ws3.write(row + 1, 2, "Total", fmt_head)
        ws3.write_number(row + 1, 3, total_sum, fmt_money)
        ws3.set_column(0, 0, 18)
        ws3.set_column(1, 1, 18)
        ws3.set_column(2, 2, 18)
        ws3.set_column(3, 3, 14)

        # --- Sheet: Bin Report (table) ---
        ws4 = wb.add_worksheet("Bin Report")
        headers = ["Date", "Manifest", "Pickup Point", "Bins"]
        for c, h in enumerate(headers):
            ws4.write(0, c, h, fmt_head)

        bin_rows = payload.get("bin_report") or payload.get("bin_report_table") or []
        row = 1
        for x in bin_rows:
            ws4.write(row, 0, str(x.get("date") or x.get("service_request_date") or ""), fmt_cell)
            ws4.write(row, 1, x.get("manifest") or x.get("name") or "", fmt_cell)
            ws4.write(row, 2, x.get("pickup_point") or x.get("pickup_point_id") or "", fmt_cell)
            ws4.write_number(row, 3, float(x.get("count") or x.get("bins") or x.get("bin_count") or 0), fmt_cell)
            row += 1

        ws4.set_column(0, 0, 14)
        ws4.set_column(1, 1, 18)
        ws4.set_column(2, 2, 30)
        ws4.set_column(3, 3, 8)

        wb.close()
        output.seek(0)

        filename = "Waste_Dashboard.xlsx"
        headers = [
            ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("Content-Disposition", f'attachment; filename="{filename}"'),
        ]
        return request.make_response(output.read(), headers=headers)
