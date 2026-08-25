"""Backend dashboard KPIs, charts, filters, and export for waste manifests."""

import json
import logging
import urllib.parse
from datetime import datetime, timedelta

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class WasteServiceRequestDashboard(models.Model):
    """Mixin: OWL dashboard data API and report/export actions."""

    _inherit = 'waste.service.request'

    def _build_dashboard_domain(self, filters=None):
        filters = filters or {}

        domain_common = []

        company, scope_domain, show_bins, show_tanks = self._company_scope_from_filters(filters)

        # ✅ apply company config restrictions everywhere
        domain_common += scope_domain

        SO = self.env["sale.order"].sudo()
        INV = self.env["account.move"].sudo()

        # ✅ allowed companies from top-right company switcher
        allowed_company_ids = self.env.companies.ids or []

        # ---------------- Safe company_id ----------------
        company_val = filters.get("company_id")
        company_id = False
        if isinstance(company_val, (list, tuple)) and company_val:
            company_id = company_val[0]
        elif isinstance(company_val, int):
            company_id = company_val
        elif isinstance(company_val, str):
            company_id = int(company_val) if company_val.isdigit() else False

        # ✅ Apply company filter:
        # - if user selected a company: force it
        # - else: use allowed companies from switcher
        if company_id:
            domain_common.append(("company_id", "=", int(company_id)))
        else:
            # IMPORTANT: so switching company in the UI actually changes dashboard
            if allowed_company_ids and "company_id" in self._fields:
                domain_common.append(("company_id", "in", allowed_company_ids))

        # ---------------- Safe partner_id (Customer) ----------------
        partner_val = filters.get("partner_id")
        partner_id = False
        if isinstance(partner_val, (list, tuple)) and partner_val:
            partner_id = partner_val[0]
        elif isinstance(partner_val, int):
            partner_id = partner_val
        elif isinstance(partner_val, str):
            partner_id = int(partner_val) if partner_val.isdigit() else False

        if partner_id:
            domain_common.append(("partner_id", "=", int(partner_id)))

        # ---------------- Manifest number ----------------
        if filters.get("manifest_number"):
            domain_common.append(("name", "ilike", filters["manifest_number"]))

        # ---------------- Ticket type ----------------
        if filters.get("ticket_type"):
            domain_common.append(("ticket_type", "=", filters["ticket_type"]))

        # ---------------- SO / Invoice filters ----------------
        so_ids = set()

        if filters.get("sale_order_number"):
            so_recs = SO.search([("name", "ilike", filters["sale_order_number"])], limit=500)
            so_ids |= set(so_recs.ids)

        if filters.get("invoice_number"):
            inv_recs = INV.search([
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("state", "!=", "cancel"),
                ("name", "ilike", filters["invoice_number"]),
            ], limit=500)

            # if you have a direct sale_order_id on invoice, use it, else fallback
            if "sale_order_id" in INV._fields:
                so_ids |= set(inv_recs.mapped("sale_order_id").ids)
            else:
                so_ids |= set(inv_recs.invoice_line_ids.mapped("sale_line_ids.order_id").ids)

        if so_ids:
            # if your manifest links to SO in another field, add alternatives here
            if "sale_order_id" in self._fields:
                domain_common.append(("sale_order_id", "in", list(so_ids)))

        # ---------------- Date filters ----------------
        domain = list(domain_common)
        if filters.get("date_from"):
            domain.append(("service_request_date", ">=", filters["date_from"]))
        if filters.get("date_to"):
            domain.append(("service_request_date", "<=", filters["date_to"]))

        return domain, domain_common

    @api.model
    def get_dashboard_kpis(self, filters=None):
        filters = filters or {}
        domain, domain_common = self._build_dashboard_domain(filters)

        today = fields.Date.context_today(self)
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())

        Request = self.env["waste.service.request"].sudo()

        open_states = ("draft", "generated", "scheduled", "dispatched")
        open_count = Request.search_count(domain + [("state", "in", open_states)])

        # Today schedule should ALSO respect same domain_common (not date range)
        schedule_field = None
        for f in ("planned_date", "scheduled_date", "schedule_date", "dispatch_date"):
            if f in self._fields:
                schedule_field = f
                break

        scheduled_today = 0
        if schedule_field:
            scheduled_today = Request.search_count(
                domain_common
                + [
                    ("state", "=", "scheduled"),
                    (schedule_field, ">=", start_of_day),
                    (schedule_field, "<=", end_of_day),
                ]
            )

        in_progress = Request.search_count(domain + [("state", "in", ("dispatched", "service_delivered"))])
        done_count = Request.search_count(domain + [("state", "=", "done")])
        rejected_count = Request.search_count(domain + [("state", "=", "cancelled")])

        month_recs = Request.search(domain + [("state", "in", ("service_delivered", "done"))])

        tank_kl = 0.0
        billing_amount = 0.0
        for rec in month_recs:
            billing_amount += (rec.billing_amount or 0.0)
            if hasattr(rec, "_is_tank_job") and rec._is_tank_job():
                tank_kl += (rec.billing_kl or 0.0)

        return {
            "open_requests": open_count,
            "scheduled_today": scheduled_today,
            "in_progress": in_progress,
            "done_count": done_count,
            "rejected_count": rejected_count,
            "tank_kl_month": tank_kl,
            "billing_amount_month": billing_amount,
        }

    def _to_date_str(self, val):
        if not val:
            return ""
        if isinstance(val, str):
            return val[:10]
        try:
            return fields.Datetime.to_string(val)[:10]
        except Exception:
            try:
                return fields.Date.to_string(val)
            except Exception:
                return ""

    def _company_scope_from_filters(self, filters=None):
        """Return (company, scope_domain, show_bins, show_tanks)."""
        filters = filters or {}

        # resolve company
        company_id = filters.get("company_id")
        try:
            company_id = int(company_id) if company_id else False
        except Exception:
            company_id = False

        company = self.env["res.company"].sudo().browse(company_id).exists() if company_id else self.env.company.sudo()

        # safe recordsets
        Service = self.env["service.request"].sudo()
        CType = self.env["container.type"].sudo()
        WType = self.env["waste.type"].sudo()

        services = company.wmz_service_ids.sudo() if "wmz_service_ids" in company._fields else Service.browse()
        ctypes = company.wmz_container_type_ids.sudo() if "wmz_container_type_ids" in company._fields else CType.browse()
        wastes = company.wmz_waste_type_ids.sudo() if "wmz_waste_type_ids" in company._fields else WType.browse()

        scope = []

        # IMPORTANT: if company configured something, restrict; if empty config -> do NOT restrict that dimension
        if services:
            scope.append(("service_requested_id", "in", services.ids))
        if ctypes and "container_type_id" in self._fields:
            scope.append(("container_type_id", "in", ctypes.ids))
        if wastes and "waste_type_id" in self._fields:
            scope.append(("waste_type_id", "in", wastes.ids))

        # Determine dashboard mode from allowed container types (name-based fallback)
        names = " ".join((ctypes.mapped("name") or [])).lower()
        show_bins = ("bin" in names) if ctypes else True
        show_tanks = ("tank" in names) if ctypes else True

        # if they configured container types but names don't include either keyword, allow both
        if ctypes and (not show_bins and not show_tanks):
            show_bins = True
            show_tanks = True

        return company, scope, show_bins, show_tanks


    # ---------------------------------------------------------
    # Dashboard payload (ALL tables/charts must use same domain)
    # ---------------------------------------------------------
    @api.model
    def get_dashboard_payload(self, filters=None):
        filters = filters or {}

        company, scope_domain, show_bins, show_tanks = self._company_scope_from_filters(filters)

        # ✅ Multi-company context (top-right company switcher)
        allowed_company_ids = self.env.companies.ids  # comes from allowed_company_ids in context

        domain, domain_common = self._build_dashboard_domain(filters)
        recs = self.with_context(allowed_company_ids=self.env.context.get("allowed_company_ids")).sudo().search(domain)

        SO = self.env["sale.order"].sudo()
        INV = self.env["account.move"].sudo()
        REQ = self.env["waste.service.request"].sudo()
        Partner = self.env["res.partner"].sudo()
        Users = self.env["res.users"].sudo()

        # ---------------- Helper ----------------
        def _date_to_str(val, fmt="%Y-%m-%d"):
            if not val:
                return ""
            if isinstance(val, str):
                return val[:10] if fmt == "%Y-%m-%d" else val[:7]
            return val.strftime(fmt)

        # ---------------- Customers dropdown ----------------
        customers_rs = Partner.search([
            ("customer_rank", ">", 0),
        ], limit=1000)
        customers = [{"id": p.id, "name": p.display_name} for p in customers_rs]

        # ---------------- MAIN DOMAIN (single truth) ----------------
        domain = self.get_dashboard_open_domain(filters)
        recs = self.sudo().search(domain)

        # ---------------- Tank kL by Customer (Y=Customer, X=kL) ----------------
        tank_by_customer = []
        if "partner_id" in self._fields and "billing_kl" in self._fields:
            totals = {}
            for m in recs:
                partner = m.partner_id.display_name if m.partner_id else "Unknown"
                totals[partner] = totals.get(partner, 0.0) + float(m.billing_kl or 0.0)

            tank_by_customer = [{"customer": k, "kl": float(v)} for k, v in totals.items()]
            tank_by_customer.sort(key=lambda x: x["kl"], reverse=True)
            tank_by_customer = tank_by_customer[:12]  # top 12

        # ---------------- KPIs ----------------
        kpis = {
            "open_requests": self.search_count(domain + [
                ("state", "in", ["draft", "generated", "scheduled", "dispatched", "service_delivered"])
            ]),
            "scheduled_count": self.search_count(domain + [("state", "=", "scheduled")]),
            "in_progress": self.search_count(
                domain + [("state", "in", ["dispatched", "service_delivered"])]),
            "done_count": self.search_count(domain + [("state", "=", "done")]),
            "rejected_count": self.search_count(domain + [("state", "=", "cancelled")]),
            "tank_kl_month": 0.0,
            "billing_amount_month": 0.0,
        }

        if not show_tanks:
            kpis["tank_kl_month"] = 0.0

        if "billing_kl" in self._fields:
            kpis["tank_kl_month"] = float(sum(recs.mapped("billing_kl") or []) or 0.0)
        if "billing_amount" in self._fields:
            kpis["billing_amount_month"] = float(sum(recs.mapped("billing_amount") or []) or 0.0)

        # ---------------- Charts ----------------
        by_status = self.read_group(domain, ["__count"], ["state"], lazy=False)
        by_service = self.read_group(domain, ["__count"], ["service_requested_id"], lazy=False)

        top_customers = self.read_group(domain, ["__count"], ["partner_id"], lazy=False)
        top_customers = sorted(top_customers, key=lambda x: x.get("__count", 0), reverse=True)[:10]

        # ---------------- Manifest Table (Summary) ----------------
        manifest_summary = []
        mf_fields = ["id", "name", "partner_id", "state", "billing_amount", "service_requested_id",
                     "service_request_date"]
        if "bin_lifted_ids" in self._fields:
            mf_fields.append("bin_lifted_ids")
        if "bin_dropped_ids" in self._fields:
            mf_fields.append("bin_dropped_ids")

        mf_rows = self.search_read(domain, mf_fields, limit=50, order="service_request_date desc")

        for r in mf_rows[:10]:
            lifted = len(r.get("bin_lifted_ids") or [])
            dropped = len(r.get("bin_dropped_ids") or [])
            manifest_summary.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "partner_id": r.get("partner_id"),
                "partner": r["partner_id"][1] if r.get("partner_id") else "",
                "state": r.get("state"),
                "service": r["service_requested_id"][1] if r.get("service_requested_id") else "",
                "service_request_date": r.get("service_request_date") or "",
                "date": _date_to_str(r.get("service_request_date"), "%Y-%m-%d"),
                "amount": float(r.get("billing_amount") or 0.0),
                "bin_lifted": lifted,
                "bin_dropped": dropped,
                "bin_count": lifted + dropped,
            })

        manifests = [{
            "id": r.get("id"),
            "name": r.get("name"),
            "customer": r["partner_id"][1] if r.get("partner_id") else "",
            "state": r.get("state"),
            "bin_count": len(r.get("bin_lifted_ids") or []) + len(r.get("bin_dropped_ids") or []),
        } for r in mf_rows]

        # ---------------- Customer by Service ----------------
        customer_by_service = []
        groups = self.read_group(domain, ["__count"], ["partner_id", "service_requested_id"], lazy=False)
        for g in groups:
            customer_by_service.append({
                "customer": g["partner_id"][1] if g.get("partner_id") else "Unknown",
                "service": g["service_requested_id"][1] if g.get("service_requested_id") else "Unknown",
                "count": g.get("__count", 0),
            })
        customer_by_service = sorted(customer_by_service, key=lambda x: x["count"], reverse=True)

        # ---------------- Driver by trips ----------------
        driver_by_trips = []
        driver_counts = {}
        if "driver_id" in self._fields:
            rows_driver = self.search_read(domain, ["driver_id"])
            for r in rows_driver:
                d = r.get("driver_id")
                if not d:
                    continue
                driver_counts[d[1]] = driver_counts.get(d[1], 0) + 1
        for name, cnt in sorted(driver_counts.items(), key=lambda x: x[1], reverse=True):
            driver_by_trips.append({"driver": name, "trips": cnt})

        # ---------------- Revenue analysis (by month) ----------------
        revenue = {}
        if "service_request_date" in self._fields and "billing_amount" in self._fields:
            rev_rows = self.search_read(domain, ["service_request_date", "billing_amount"])
            for r in rev_rows:
                dt = r.get("service_request_date")
                if not dt:
                    continue
                key = _date_to_str(dt, "%Y-%m")
                revenue[key] = revenue.get(key, 0.0) + float(r.get("billing_amount") or 0.0)
        revenue_analysis = [{"label": k, "amount": float(v)} for k, v in sorted(revenue.items())]

        revenue_by_customer = []
        if "partner_id" in self._fields and "billing_amount" in self._fields:
            totals = {}
            for m in recs:
                partner = m.partner_id.display_name if m.partner_id else "Unknown"
                totals[partner] = totals.get(partner, 0.0) + float(m.billing_amount or 0.0)

            revenue_by_customer = [{"customer": k, "amount": float(v)} for k, v in totals.items()]
            revenue_by_customer.sort(key=lambda x: x["amount"], reverse=True)
            revenue_by_customer = revenue_by_customer[:12]  # top 12

        # ✅ Multi-company context (top-right company switcher)
        allowed_company_ids = self.env.context.get("allowed_company_ids") or self.env.companies.ids or []

        # ✅ Revenue by Company (SAFE even if billing_amount is computed/non-stored)
        revenue_by_company = []
        if "company_id" in self._fields and "billing_amount" in self._fields:
            totals = {}  # key: company_id (or 0) -> {"company": name, "amount": float}

            for m in recs:
                c = m.company_id
                cid = c.id if c else 0
                cname = c.display_name if c else "No Company"

                if cid not in totals:
                    totals[cid] = {"company": cname, "amount": 0.0}

                # IMPORTANT: read_group often returns 0 when field is computed.
                # This uses record values directly.
                totals[cid]["amount"] += float(m.billing_amount or 0.0)

            revenue_by_company = sorted(totals.values(), key=lambda x: x["amount"], reverse=True)

        _logger.info("Revenue by company result: %s", revenue_by_company)

        # ✅ Companies dropdown (only allowed companies from switcher)
        companies_rs = self.env["res.company"].sudo().browse(self.env.companies.ids).exists()
        companies = [{"id": c.id, "name": c.name} for c in companies_rs]

        gran = filters.get("tank_granularity") or "day"
        now = fields.Datetime.now()

        if filters.get("date_from"):
            df = filters["date_from"]
            start = fields.Datetime.from_string((df + " 00:00:00") if isinstance(df, str) else df)
        else:
            start = now - timedelta(days=180 if gran == "week" else 60)

        tank_domain = list(domain) + [
            ("service_request_date", ">=", fields.Datetime.to_string(start)),
            ("service_request_date", "<=", fields.Datetime.to_string(now)),
        ]

        tank_domain_with_type = list(tank_domain)
        if "container_type_id" in self._fields:
            tank_domain_with_type += [("container_type_id.name", "ilike", "tank")]

        use_domain = tank_domain_with_type if self.search_count(tank_domain_with_type) else tank_domain

        tank_series = []
        if "billing_kl" in self._fields:
            tank_rows = self.search_read(use_domain, ["service_request_date", "billing_kl"])
            bucket = {}
            for r in tank_rows:
                dt = r.get("service_request_date")
                if not dt:
                    continue
                dt_obj = fields.Datetime.from_string(dt) if isinstance(dt, str) else dt
                if gran == "week":
                    iso = dt_obj.isocalendar()
                    key = f"{iso.year}-W{iso.week:02d}"
                else:
                    key = dt_obj.strftime("%Y-%m-%d")
                bucket[key] = bucket.get(key, 0.0) + float(r.get("billing_kl") or 0.0)

            tank_series = [{"label": k, "kl": float(v)} for k, v in sorted(bucket.items(), key=lambda x: x[0])]

        # ---------------- Today schedule + assignment pie ----------------
        schedule_states = ["scheduled", "dispatched"]
        schedule_field = None
        for f in ("planned_date", "scheduled_date", "schedule_date", "dispatch_date"):
            if f in self._fields:
                schedule_field = f
                break

        todays = []
        assignment_pie = {"labels": ["Driver Jobs", "Service Provider Jobs"], "values": [0, 0]}

        if schedule_field:
            today_local = fields.Date.context_today(self)
            broad_domain = list(domain) + [
                ("state", "in", schedule_states),
                (schedule_field, "!=", False),
            ]
            today_fields = ["id", "name", "partner_id", schedule_field, "vehicle_id", "driver_id", "state",
                            "is_service_provider", "provider_id"]
            today_fields = [f for f in today_fields if f in self._fields]

            candidates = self.search_read(broad_domain, today_fields, order=f"{schedule_field} asc", limit=500)

            filtered = []
            for r in candidates:
                dt = r.get(schedule_field)
                if not dt:
                    continue
                dt_utc = fields.Datetime.from_string(dt) if isinstance(dt, str) else dt
                dt_local = fields.Datetime.context_timestamp(self, dt_utc)
                if dt_local.date() == today_local:
                    filtered.append(r)

            todays = filtered

            sp_count = 0
            driver_count = 0
            for r in todays:
                if r.get("is_service_provider") or r.get("provider_id"):
                    sp_count += 1
                else:
                    driver_count += 1

            assignment_pie = {
                "labels": ["Driver Jobs", "Service Provider Jobs"],
                "values": [driver_count, sp_count],
            }

        # ---------------- Users pie ----------------
        user_domain = []
        if filters.get("company_id"):
            user_domain.append(("company_id", "=", int(filters["company_id"])))

        if filters.get("partner_id"):
            pid = int(filters["partner_id"])
            pids = Partner.search([("id", "child_of", pid)]).ids
            user_domain.append(("partner_id", "in", pids or [pid]))

        active_users = Users.search(user_domain + [("active", "=", True)])
        inactive_count = Users.search_count(user_domain + [("active", "=", False)])

        internal_active = active_users.filtered(lambda u: u.has_group("base.group_user"))
        portal_active = active_users.filtered(
            lambda u: u.has_group("base.group_portal") and not u.has_group("base.group_user"))

        users_pie = {
            "labels": ["Internal (Active)", "Portal (Active)", "Inactive"],
            "values": [len(internal_active), len(portal_active), int(inactive_count)],
        }

        # ---------------- Bin Report (Dropped) TABLE ----------------
        bin_report_table = []
        bin_dropped_field = "bin_dropped_ids"

        if bin_dropped_field in self._fields:
            drop_rows = self.search_read(
                domain,
                [f for f in [
                    "id", "name", "pickup_point_id", "pickup_point_ids", "dropoff_point_ids",
                    "bin_line_ids", bin_dropped_field, "service_request_date",
                ] if f in self._fields],
                limit=80,
                order="service_request_date desc"
            )

            def _get_point_label_from_row(row):
                if row.get("pickup_point_id"):
                    return row["pickup_point_id"][1]

                line_ids = row.get("bin_line_ids") or []
                if line_ids:
                    Line = self.env["waste.request.bin.line"].sudo()
                    line = Line.browse(line_ids[0]).exists()
                    if line:
                        if getattr(line, "dropoff_point_id", False):
                            return line.dropoff_point_id.display_name
                        if getattr(line, "pickup_point_id", False):
                            return line.pickup_point_id.display_name

                pp_ids = row.get("pickup_point_ids") or []
                dp_ids = row.get("dropoff_point_ids") or []
                all_ids = dp_ids or pp_ids
                if all_ids:
                    pts = self.env["pickup.point"].sudo().browse(all_ids).exists()
                    return ", ".join(pts.mapped("display_name"))
                return ""

            all_container_ids = set()
            for r in drop_rows:
                for cid in (r.get(bin_dropped_field) or []):
                    all_container_ids.add(cid)

            container_name_map = {}
            if all_container_ids:
                Container = self.env["waste.container"].sudo() if "waste.container" in self.env else self.env[
                    "stock.lot"].sudo()
                for c in Container.browse(list(all_container_ids)).exists():
                    container_name_map[c.id] = c.display_name

            for r in drop_rows:
                manifest_name = r.get("name") or ""
                drop_point = _get_point_label_from_row(r)
                date_str = _date_to_str(r.get("service_request_date"), "%Y-%m-%d")

                for cid in (r.get(bin_dropped_field) or []):
                    bin_report_table.append({
                        "key": f"{manifest_name}:{cid}",
                        "manifest": manifest_name,
                        "dropoff_point": drop_point,
                        "bin": container_name_map.get(cid, str(cid)),
                        "date": date_str,
                        "request_id": [r.get("id"), manifest_name] if r.get("id") else False,
                    })

            bin_report_table = bin_report_table[:10]

        # ---------------- Bin Report (CHART) ----------------
        lifted_total = 0
        dropped_total = 0

        if "bin_lifted_ids" in self._fields:
            for r in self.search_read(domain, ["bin_lifted_ids"]):
                lifted_total += len(r.get("bin_lifted_ids") or [])
        if "bin_dropped_ids" in self._fields:
            for r in self.search_read(domain, ["bin_dropped_ids"]):
                dropped_total += len(r.get("bin_dropped_ids") or [])

        bin_report = [
            {"label": "Bins Lifted", "count": int(lifted_total)},
            {"label": "Bins Dropped", "count": int(dropped_total)},
        ]
        # bin_report_chart = [{"label": "Total Bins Lifted", "count": int(lifted_total)}]

        bin_report_chart = [
            {"label": "Bins Lifted", "count": int(lifted_total)},
            {"label": "Bins Dropped", "count": int(dropped_total)},
        ]

        # ---------------- Bin Revenue (TABLE + CHART) ----------------
        bin_revenue_table = []
        bin_revenue_chart = []

        has_bins = ("bin_lifted_ids" in self._fields) or ("bin_dropped_ids" in self._fields)
        if has_bins and ("sale_order_id" in self._fields):
            rev_fields = ["sale_order_id", "order_line_id", "service_request_date"]
            if "bin_lifted_ids" in self._fields:
                rev_fields.append("bin_lifted_ids")
            if "bin_dropped_ids" in self._fields:
                rev_fields.append("bin_dropped_ids")

            rev_rows = self.sudo().search_read(domain, rev_fields, limit=2000)

            all_container_ids = set()
            for r in rev_rows:
                for cid in (r.get("bin_lifted_ids") or []):
                    all_container_ids.add(cid)
                for cid in (r.get("bin_dropped_ids") or []):
                    all_container_ids.add(cid)

            container_name_map = {}
            if all_container_ids:
                Container = self.env["waste.container"].sudo() if "waste.container" in self.env else self.env[
                    "stock.lot"].sudo()
                for c in Container.browse(list(all_container_ids)).exists():
                    container_name_map[c.id] = c.display_name

            per_bin = {}
            SOL = self.env["sale.order.line"].sudo()

            for r in rev_rows:
                lifted_ids = r.get("bin_lifted_ids") or []
                dropped_ids = r.get("bin_dropped_ids") or []
                bin_ids = list(set(lifted_ids + dropped_ids))
                if not bin_ids:
                    continue

                so_id = r.get("sale_order_id") and r["sale_order_id"][0]
                if not so_id:
                    continue

                line = False
                if r.get("order_line_id"):
                    line = SOL.browse(r["order_line_id"][0]).exists()

                if not line:
                    so = SO.browse(so_id).exists()
                    line = so.order_line[:1] if so else False

                if not line:
                    continue

                qty = float(line.product_uom_qty or 0.0)
                if qty <= 0:
                    continue

                subtotal = float(line.price_subtotal or 0.0)
                per_bin_amount = subtotal / qty if subtotal else 0.0

                for bid in bin_ids:
                    rec = per_bin.setdefault(bid, {
                        "revenue": 0.0, "trips": 0, "lifted": 0, "dropped": 0,
                        "qty": 0.0, "price_unit": 0.0, "line_total": 0.0
                    })
                    rec["revenue"] += per_bin_amount
                    rec["trips"] += 1
                    if bid in lifted_ids:
                        rec["lifted"] += 1
                    if bid in dropped_ids:
                        rec["dropped"] += 1

                    rec["qty"] = qty
                    rec["price_unit"] = float(line.price_unit or 0.0)
                    rec["line_total"] = subtotal

            top = sorted(per_bin.items(), key=lambda x: x[1]["revenue"], reverse=True)[:10]
            for bid, vals in top:
                bin_revenue_table.append({
                    "key": f"binrev:{bid}",
                    "bin_id": bid,
                    "bin": container_name_map.get(bid, str(bid)),
                    "revenue": float(vals["revenue"]),
                    "trips": int(vals["trips"]),
                    "lifted": int(vals["lifted"]),
                    "dropped": int(vals["dropped"]),
                    "so_qty": float(vals["qty"]),
                    "so_price_unit": float(vals["price_unit"]),
                    "so_line_total": float(vals["line_total"]),
                })

            # ✅ IMPORTANT: include bin_id so chart click can open correct domain
            bin_revenue_chart = [{
                "bin_id": row["bin_id"],
                "label": row["bin"],
                "amount": row["revenue"],
            } for row in bin_revenue_table]

        # ---------------------------------------------------------
        # Sales Order ↔ Invoice (Totals) — MUST follow current manifest domain
        # ---------------------------------------------------------
        # Manifests currently shown by current dashboard domain (may be 1 or many)
        manifest_ids_current = recs.ids

        # SOs linked to those manifests (via manifest.sale_order_id)
        so_ids_linked = set()
        if "sale_order_id" in self._fields and manifest_ids_current:
            so_ids_linked = set(recs.mapped("sale_order_id").ids)

        # Base invoice domain
        inv_domain = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "!=", "cancel"),
        ]

        # Invoice number filter (if user typed it)
        if filters.get("invoice_number"):
            inv_domain.append(("name", "ilike", filters["invoice_number"]))

        # Customer tree filter for invoices
        partner_ids = []
        if filters.get("partner_id"):
            pid = int(filters["partner_id"])
            partner_ids = Partner.search([("id", "child_of", pid)]).ids
        if partner_ids:
            inv_domain.append(("partner_id", "in", partner_ids))

        # ✅ IMPORTANT: Keep invoices inside current manifest scope:
        # (direct invoice → manifest) OR (invoice lines → SO linked to manifest)
        scope_parts = []

        # Direct link: account.move.service_request_id -> waste.service.request
        if manifest_ids_current and ("service_request_id" in INV._fields):
            scope_parts.append(("service_request_id", "in", manifest_ids_current))

        # Indirect link: invoice_line -> sale_line -> sale_order (linked to manifests)
        if so_ids_linked:
            scope_parts.append(("invoice_line_ids.sale_line_ids.order_id", "in", list(so_ids_linked)))

        # Apply scope
        if scope_parts:
            if len(scope_parts) == 1:
                inv_domain.append(scope_parts[0])
            else:
                # prepend OR operators: for N conditions you need N-1 "|"
                inv_domain += ["|"] * (len(scope_parts) - 1) + scope_parts

            invoices = INV.search(inv_domain, limit=200)
        else:
            invoices = INV.browse([])

        # Build table rows
        so_invoice_map = []
        for inv in invoices:
            so_recs = inv.invoice_line_ids.mapped("sale_line_ids.order_id")

            # If invoice has SOs, create rows per SO
            if so_recs:
                for so in so_recs:
                    # If we have a manifest SO scope, keep only those SOs
                    if so_ids_linked and so.id not in so_ids_linked:
                        continue
                    so_invoice_map.append({
                        "key": f"{so.name}|{inv.name}",
                        "sale_order": so.name,
                        "invoice": inv.name,
                        "total": float(inv.amount_total or 0.0),
                        "invoice_id": [inv.id, inv.name],
                    })
            else:
                # Invoice linked directly to manifest (service_request_id) but no SO lines
                so_invoice_map.append({
                    "key": f"NOSO|{inv.name}",
                    "sale_order": "",
                    "invoice": inv.name,
                    "total": float(inv.amount_total or 0.0),
                    "invoice_id": [inv.id, inv.name],
                })

        # Limit visible rows
        so_invoice_totals = [{
            "key": x["key"],
            "sale_order": x["sale_order"],
            "invoice": x["invoice"],
            "total": x["total"],
            "invoice_id": x["invoice_id"],
        } for x in so_invoice_map[:10]]

        # ---------------- Sales Orders by Customer (must work even if no linked SOs) ----------------
        so_by_customer = []

        so_domain = []
        # optional: limit to SOs linked to current manifests if available
        if so_ids_linked:
            so_domain.append(("id", "in", list(so_ids_linked)))

        # apply date filters to SO
        if filters.get("date_from"):
            so_domain.append(("date_order", ">=", filters["date_from"]))
        if filters.get("date_to"):
            so_domain.append(("date_order", "<=", filters["date_to"]))

        # apply SO number filter
        if filters.get("sale_order_number"):
            so_domain.append(("name", "ilike", filters["sale_order_number"]))

        # partner tree filter
        so_partner_ids = []
        if filters.get("partner_id"):
            pid = int(filters["partner_id"])
            so_partner_ids = Partner.search([("id", "child_of", pid)]).ids
            so_domain.append(("partner_id", "in", so_partner_ids or [pid]))

        # if there is no domain at all, avoid read_group on []
        if so_domain:
            so_groups = SO.read_group(so_domain, ["__count"], ["partner_id"], lazy=False)
        else:
            so_groups = []

        for g in so_groups:
            so_by_customer.append({
                "customer": g["partner_id"][1] if g.get("partner_id") else "Unknown",
                "count": g.get("__count", 0),
            })

        so_by_customer = sorted(so_by_customer, key=lambda x: x["count"], reverse=True)

        so_by_manifest = []

        if not show_bins:
            bin_report_table = []
            bin_report = []
            bin_report_chart = []
            bin_revenue_table = []
            bin_revenue_chart = []

        if not show_tanks:
            tank_series = []
            tank_by_customer = []

        return {
            "customers": customers,
            "companies": companies,  # ✅ NEW
            "kpis": kpis,
            "by_status": by_status,
            "by_service": by_service,
            "top_customers": top_customers,
            "tank_series": tank_series,
            "todays": todays,
            "assignment_pie": assignment_pie,
            "users_pie": users_pie,

            "manifest_summary": manifest_summary,
            "manifests": manifests,

            "so_invoice_totals": so_invoice_totals,
            "so_invoice_map": so_invoice_map,

            "bin_report_table": bin_report_table,
            "bin_report": bin_report,
            "bin_report_chart": bin_report_chart,

            "bin_revenue_table": bin_revenue_table,
            "bin_revenue_chart": bin_revenue_chart,

            "customer_by_service": customer_by_service,
            "driver_by_trips": driver_by_trips,
            "revenue_analysis": revenue_analysis,
            "revenue_by_customer": revenue_by_customer,
            "tank_by_customer": tank_by_customer,
            "revenue_by_company": revenue_by_company,

            "so_by_customer": so_by_customer,
            "so_by_manifest": so_by_manifest,

            "mode": {
                "show_bins": bool(show_bins),
                "show_tanks": bool(show_tanks),
                "company_id": company.id,
                "company_name": company.name,
            },

        }

    @api.model
    def get_dashboard_open_domain(self, filters=None):
        domain, _domain_common = self._build_dashboard_domain(filters or {})
        return domain

    @api.model
    def action_print_dashboard_report(self, filters=None):
        """Print the waste dashboard PDF with applied filters."""
        filters = filters or {}
        domain, _domain_common = self._build_dashboard_domain(filters)
        docs = self.search(domain, order="service_request_date desc")
        data = {"filters": filters, "printed_at": fields.Datetime.now()}
        return self.env.ref("waste_management_zakheni.action_waste_dashboard_report_pdf").report_action(docs, data=data)

    @api.model
    def action_export_dashboard_xlsx(self, filters=None):
        """
        Called from JS: returns an URL action to download the XLSX.
        Filters are passed through to the controller.
        """
        filters = filters or {}
        filters_json = urllib.parse.quote(json.dumps(filters))
        return {
            "type": "ir.actions.act_url",
            "url": f"/waste_dashboard/export_xlsx?filters={filters_json}",
            "target": "self",
        }
