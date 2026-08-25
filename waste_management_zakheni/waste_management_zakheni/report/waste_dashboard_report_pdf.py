# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ReportWasteDashboardPDF(models.AbstractModel):
    _name = "report.waste_management_zakheni.waste_dashboard_report_pdf"
    _description = "Waste Dashboard PDF Report"

    def _date_str(self, dtval):
        if not dtval:
            return ""
        if isinstance(dtval, str):
            return dtval[:10]
        return fields.Datetime.to_string(dtval)[:10]

    def _safe_int(self, v):
        """Accept int/str('12')/[12,'Name'] else False (ignores 'All Customers')."""
        if not v:
            return False
        if isinstance(v, (list, tuple)) and v:
            v = v[0]
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            s = v.strip()
            if s.isdigit():
                return int(s)
            return False
        try:
            return int(v)
        except Exception:
            return False

    def _build_domain_from_filters(self, filters):
        """Build a safe domain from dashboard filters."""
        filters = filters or {}
        domain = []

        # dates + manifest
        if filters.get("date_from"):
            domain.append(("service_request_date", ">=", filters["date_from"]))
        if filters.get("date_to"):
            domain.append(("service_request_date", "<=", filters["date_to"]))
        if filters.get("manifest_number"):
            domain.append(("name", "ilike", filters["manifest_number"]))

        # company/customer/ticket
        company_id = self._safe_int(filters.get("company_id"))
        if company_id:
            domain.append(("company_id", "=", company_id))

        partner_id = self._safe_int(filters.get("partner_id"))
        if partner_id:
            domain.append(("partner_id", "=", partner_id))

        if filters.get("ticket_type"):
            domain.append(("ticket_type", "=", filters["ticket_type"]))

        return domain

    # ---------------- helper: find SO for a manifest ----------------
    def _manifest_so(self, m):
        # try common field names safely
        for f in ("sale_order_id", "order_id", "so_id"):
            if f in m._fields and getattr(m, f):
                return getattr(m, f)
        for f in ("sale_order_ids", "order_ids", "so_ids"):
            if f in m._fields:
                rel = getattr(m, f)
                if rel:
                    return rel[0]
        if "order_line_id" in m._fields and m.order_line_id:
            return m.order_line_id.order_id
        return False

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        filters = (data.get("filters") or {}).copy()

        Request = self.env["waste.service.request"].sudo()
        INV = self.env["account.move"].sudo()

        # ✅ Build base domain from filters
        base_domain = self._build_domain_from_filters(filters)

        # ✅ If docids provided (printing from selected records), honor them
        domain = list(base_domain)
        if docids:
            domain = [("id", "in", docids)] + domain

        manifests = Request.search(domain, order="service_request_date desc")

        # ---------------- KPI (MUST MATCH QWEB KEYS) ----------------
        open_states = ["draft", "generated", "scheduled", "dispatched", "service_delivered"]

        # IMPORTANT: use base_domain (not row-level SO/INV filters) for KPI counts
        kpis_domain = list(base_domain)
        if docids:
            kpis_domain = [("id", "in", docids)] + kpis_domain

        kpis = {
            "open": Request.search_count(kpis_domain + [("state", "in", open_states)]),
            "scheduled": Request.search_count(kpis_domain + [("state", "=", "scheduled")]),
            "in_progress": Request.search_count(
                kpis_domain + [("state", "in", ["dispatched", "service_delivered"])]
            ),
            "done": Request.search_count(kpis_domain + [("state", "=", "done")]),
            "rejected": Request.search_count(
                kpis_domain + ["|", ("state", "=", "cancelled"), ("is_rejected", "=", True)]
            ),
        }

        # ---------------- rows ----------------
        report_rows = []
        so_inv_rows = []
        total_invoices = 0.0

        # row-level filters (SO/Invoice)
        so_filter_text = (filters.get("sale_order_number") or "").strip().lower()
        inv_filter_text = (filters.get("invoice_number") or "").strip().lower()

        for m in manifests:
            lifted = len(m.bin_lifted_ids) if "bin_lifted_ids" in m._fields else 0
            dropped = len(m.bin_dropped_ids) if "bin_dropped_ids" in m._fields else 0

            so_name = ""
            inv_name = ""
            inv_rec = False  # ✅ keep invoice record for totals safely

            so = self._manifest_so(m)
            if so:
                so_name = so.name or ""

                # invoices linked to SO (best)
                invs = getattr(so, "invoice_ids", False)
                if invs:
                    invs = invs.filtered(lambda x: x.move_type in ("out_invoice", "out_refund") and x.state != "cancel")
                else:
                    invs = INV.search(
                        [
                            ("move_type", "in", ["out_invoice", "out_refund"]),
                            ("state", "!=", "cancel"),
                            ("invoice_origin", "ilike", so.name),
                        ],
                        order="invoice_date desc, id desc",
                        limit=10,
                    )

                inv_rec = invs[:1] if invs else False
                if inv_rec:
                    inv_name = inv_rec.name or ""

            # ✅ Apply extra filters (SO/Invoice) at row level (does NOT affect KPIs)
            if so_filter_text and so_filter_text not in (so_name or "").lower():
                continue
            if inv_filter_text and inv_filter_text not in (inv_name or "").lower():
                continue

            report_rows.append(
                {
                    "manifest": m.name or "",
                    "customer": m.partner_id.display_name if m.partner_id else "",
                    "date": self._date_str(m.service_request_date),
                    "status": m.state or "",
                    "bin_count": lifted + dropped,
                    "so": so_name,
                    "invoice": inv_name,
                }
            )

            # ✅ Totals table
            if so_name and inv_name and inv_rec:
                amount = float(inv_rec.amount_total or 0.0)
                total_invoices += amount
                so_inv_rows.append(
                    {
                        "manifest": m.name or "",
                        "sale_order": so_name,
                        "invoice": inv_name,
                        "total": amount,
                    }
                )

        # ✅ sort totals rows (optional)
        so_inv_rows = sorted(so_inv_rows, key=lambda x: (x.get("sale_order") or "", x.get("invoice") or ""))

        return {
            "doc_ids": manifests.ids,
            "doc_model": "waste.service.request",
            "docs": manifests,

            "filters": filters,
            "printed_at": fields.Datetime.now(),
            "user": self.env.user,

            "kpis": kpis,
            "manifest_rows": report_rows,
            "so_inv_rows": so_inv_rows,
            "so_inv_total": float(total_invoices or 0.0),
        }



# # -*- coding: utf-8 -*-
# from odoo import api, fields, models
#
#
# class ReportWasteDashboardPDF(models.AbstractModel):
#     # ✅ MUST MATCH report_name:
#     # report.<module>.<report_name>
#     _name = "report.waste_management_zakheni.waste_dashboard_report_pdf"
#     _description = "Waste Dashboard PDF Report"
#
#     def _date_str(self, dtval):
#         if not dtval:
#             return ""
#         if isinstance(dtval, str):
#             return dtval[:10]
#         return fields.Datetime.to_string(dtval)[:10]
#
#     @api.model
#     def _get_report_values(self, docids, data=None):
#         data = data or {}
#         filters = (data.get("filters") or {})
#
#         Request = self.env["waste.service.request"].sudo()
#         INV = self.env["account.move"].sudo()
#         SO = self.env["sale.order"].sudo()
#
#         # ---------------- Domain (filters) ----------------
#         domain = []
#
#         if filters.get("date_from"):
#             domain.append(("service_request_date", ">=", filters["date_from"]))
#         if filters.get("date_to"):
#             domain.append(("service_request_date", "<=", filters["date_to"]))
#         if filters.get("manifest_number"):
#             domain.append(("name", "ilike", filters["manifest_number"]))
#
#         if filters.get("company_id"):
#             domain.append(("company_id", "=", int(filters["company_id"])))
#         if filters.get("partner_id"):
#             domain.append(("partner_id", "=", int(filters["partner_id"])))
#         if filters.get("ticket_type"):
#             domain.append(("ticket_type", "=", filters["ticket_type"]))
#
#         # ✅ If docids provided (printing from selected records), honor them
#         if docids:
#             domain = [("id", "in", docids)] + domain
#
#         manifests = Request.search(domain, order="service_request_date desc")
#
#         # ---------------- KPI ----------------
#         open_states = ["draft", "generated", "scheduled", "dispatched", "service_delivered"]
#         kpis = {
#             "open": Request.search_count(domain + [("state", "in", open_states)]),
#             "scheduled": Request.search_count(domain + [("state", "=", "scheduled")]),
#             "in_progress": Request.search_count(domain + [("state", "in", ["assigned", "dispatched", "service_delivered"])]),
#             "done": Request.search_count(domain + [("state", "=", "done")]),
#             "rejected": Request.search_count(domain + ["|", ("state", "=", "cancelled"), ("is_rejected", "=", True)]),
#         }
#
#         # ---------------- helper: find SO for a manifest ----------------
#         def _manifest_so(m):
#             # try common field names safely
#             for f in ("sale_order_id", "order_id", "so_id"):
#                 if f in m._fields and getattr(m, f):
#                     return getattr(m, f)
#             for f in ("sale_order_ids", "order_ids", "so_ids"):
#                 if f in m._fields:
#                     rel = getattr(m, f)
#                     if rel:
#                         return rel[0]
#             if "order_line_id" in m._fields and m.order_line_id:
#                 return m.order_line_id.order_id
#             return False
#
#         # ---------------- rows ----------------
#         report_rows = []
#         so_inv_rows = []
#         total_invoices = 0.0
#
#         # optional filter by SO/Invoice text (works even if no direct manifest relation)
#         so_filter_text = (filters.get("sale_order_number") or "").strip().lower()
#         inv_filter_text = (filters.get("invoice_number") or "").strip().lower()
#
#         for m in manifests:
#             lifted = len(m.bin_lifted_ids) if "bin_lifted_ids" in m._fields else 0
#             dropped = len(m.bin_dropped_ids) if "bin_dropped_ids" in m._fields else 0
#
#             so_name = ""
#             inv_name = ""
#
#             so = _manifest_so(m)
#             if so:
#                 so_name = so.name or ""
#
#                 # invoices linked to SO (best)
#                 invs = getattr(so, "invoice_ids", False)
#                 if not invs:
#                     invs = INV.search(
#                         [("move_type", "in", ["out_invoice", "out_refund"]),
#                          ("state", "!=", "cancel"),
#                          ("invoice_origin", "ilike", so.name)],
#                         order="invoice_date desc, id desc",
#                         limit=10
#                     )
#
#                 inv = invs[:1] if invs else False
#                 if inv:
#                     inv_name = inv.name or ""
#
#             # apply extra filters (SO/Invoice) at row level
#             if so_filter_text and so_filter_text not in (so_name or "").lower():
#                 continue
#             if inv_filter_text and inv_filter_text not in (inv_name or "").lower():
#                 continue
#
#             report_rows.append({
#                 "manifest": m.name or "",
#                 "customer": m.partner_id.display_name if m.partner_id else "",
#                 "date": self._date_str(m.service_request_date),
#                 "status": m.state or "",
#                 "bin_count": lifted + dropped,
#                 "so": so_name,
#                 "invoice": inv_name,
#             })
#
#             if so_name and inv_name and inv:
#                 amount = float(inv.amount_total or 0.0)
#                 total_invoices += amount
#                 so_inv_rows.append({
#                     "manifest": m.name or "",
#                     "sale_order": so_name,
#                     "invoice": inv_name,
#                     "total": amount,
#                 })
#
#         return {
#             "doc_ids": manifests.ids,
#             "doc_model": "waste.service.request",
#             "docs": manifests,
#
#             "filters": filters,
#             "printed_at": fields.Datetime.now(),  # ✅ used by QWeb
#             "user": self.env.user,                # ✅ used by QWeb
#
#             "kpis": kpis,
#             "manifest_rows": report_rows,
#             "so_inv_rows": so_inv_rows,
#             "so_inv_total": float(total_invoices or 0.0),
#         }
