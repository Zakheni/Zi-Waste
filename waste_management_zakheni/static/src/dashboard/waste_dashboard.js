/** @odoo-module **/

import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class WasteDashboard extends Component {
  static template = "waste_management_zakheni.WasteDashboard";

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");

    this.state = useState({
      loading: true,

      filters: {
        company_id: false,
        partner_id: false,
        ticket_type: false,
        date_from: false,
        date_to: false,
        manifest_number: "",
        sale_order_number: "",
        invoice_number: "",
        tank_granularity: "day",
      },

      kpis: {
        open_requests: 0,
        scheduled_count: 0,
        in_progress: 0,
        done_count: 0,
        rejected_count: 0,
        tank_kl_month: 0,
        billing_amount_month: 0,
      },

      busy: { vehicles: [], drivers: [], assistants: [] },
      todays: [],

      // summary tables (XML loops over these, must ALWAYS be arrays)
      manifest_summary: [],
      so_invoice_totals: [],
      bin_report: [],

      // chart instances
      statusChart: null,
      serviceChart: null,
      topCustomersChart: null,
      tankChart: null,
      assignmentPieChart: null,
      usersPieChart: null,

      customerServiceChart: null,
      driverTripsChart: null,
      revenueChart: null,
      binChart: null,
      soCustomerChart: null,
    });

    // refs (must match XML t-ref="")
    this.statusCanvas = useRef("statusCanvas");
    this.serviceCanvas = useRef("serviceCanvas");
    this.topCustomersCanvas = useRef("topCustomersCanvas");
    this.tankCanvas = useRef("tankCanvas");
    this.assignmentPieCanvas = useRef("assignmentPieCanvas");
    this.usersPieCanvas = useRef("usersPieCanvas");

    this.customerServiceCanvas = useRef("customerServiceCanvas");
    this.driverTripsCanvas = useRef("driverTripsCanvas");
    this.revenueCanvas = useRef("revenueCanvas");
    this.binCanvas = useRef("binCanvas");
    this.soCustomerCanvas = useRef("soCustomerCanvas");

    // datasets (always arrays)
    this._statusGroups = [];
    this._serviceGroups = [];
    this._topCustomers = [];
    this._tankSeries = [];
    this._assignmentPie = { labels: [], values: [] };
    this._usersPie = { labels: [], values: [] };

    this._customerByService = [];
    this._driverTrips = [];
    this._revenueAnalysis = [];
    this._binReportChart = [];
    this._soByCustomer = [];

    // handlers
    this.onRefresh = () => this.refreshAndRender();
    this.onTankDay = () => this.setTankGranularity("day");
    this.onTankWeek = () => this.setTankGranularity("week");
    this.onApplyFilters = () => this.refreshAndRender();
    this.onClearFilters = () => this.clearFilters();

     // ✅ bind methods so "this" is always the component instance
    this.openTodayRow = this.openTodayRow.bind(this);
    this.openManifestRow = this.openManifestRow.bind(this);
    this.openInvoiceTotalsRow = this.openInvoiceTotalsRow.bind(this);
    this.openBinReportRow = this.openBinReportRow.bind(this);
    this.openRequests = this.openRequests.bind(this);


    // KPI clicks
    this.openOpenClick = () =>
      this.openRequests(
        [["state", "in", ["draft", "generated", "scheduled", "assigned", "dispatched", "service_delivered"]]],
        "Open Requests"
      );
    this.openScheduledClick = () => this.openRequests([["state", "=", "scheduled"]], "Scheduled");
    this.openInProgressClick = () =>
      this.openRequests([["state", "in", ["assigned", "dispatched", "service_delivered"]]], "In Progress");
    this.openDoneClick = () => this.openRequests([["state", "=", "done"]], "Authorised");
//    this.openRejectedClick = () =>

    this.openRejectedClick = () =>
      this.openRequests([["state", "=", "cancelled"]], "Rejected / Flagged");

    // Today list + row
    this.openTodayListClick = () =>
      this.openRequests([["state", "in", ["scheduled", "assigned", "dispatched"]]], "Today Schedule");
    this.openTodayRowClick = (rec) => this.openTodayRow(rec);

    // Summary tables
    this.openManifestList = () => this.openManifestListAction();
    this.openManifestRowClick = (row) => this.openManifestRow(row);

    this.openInvoiceTotalsList = () => this.openInvoiceTotalsListAction();
    this.openInvoiceTotalsRowClick = (row) => this.openInvoiceTotalsRow(row);

    this.openBinReportList = () => this.openBinReportListAction();
    this.openBinReportRowClick = (row) => this.openBinReportRow(row);


    this.printDashboard = async () => {
    const action = await this.orm.call(
        "waste.service.request",
        "action_print_dashboard_report",
        [this.state.filters]   // ✅ SEND FILTERS
    );
    this.action.doAction(action);
};

    onWillStart(async () => {
      await this.ensureChartJS();
    });

    onMounted(async () => {
      await this.afterPaint();
      this.renderCharts(); // empty first
      await this.refreshAndRender(); // load + redraw
    });
  }

  // ---------------- utils ----------------
  _arr(x) {
    return Array.isArray(x) ? x : [];
  }

  _ctx(ref) {
    return ref && ref.el ? ref.el.getContext("2d") : null;
  }

  _destroyCharts(keys) {
    keys.forEach((k) => {
      if (this.state[k]) {
        try {
          this.state[k].destroy();
        } catch (e) {}
      }
      this.state[k] = null;
    });
  }

  async ensureChartJS() {
    if (window.Chart) return;
    const candidates = ["/web/static/lib/chartjs/chart.umd.js", "/web/static/lib/Chart/Chart.js"];
    for (const url of candidates) {
      try {
        await loadJS(url);
        if (window.Chart) return;
      } catch (e) {}
    }
    console.warn("Chart.js not available. Ensure it's added to web.assets_backend.");
  }

  async afterPaint() {
    await new Promise((r) => requestAnimationFrame(r));
  }

  async setTankGranularity(g) {
    this.state.filters.tank_granularity = g;
    await this.refreshAndRender();
  }

  async clearFilters() {
    this.state.filters.date_from = false;
    this.state.filters.date_to = false;
    this.state.filters.manifest_number = "";
    this.state.filters.sale_order_number = "";
    this.state.filters.invoice_number = "";
    await this.refreshAndRender();
  }

  async refreshAndRender() {
    this.state.loading = true;
    await this.afterPaint();

    await this.loadAll();

    this.state.loading = false;
    await this.afterPaint();

    this.renderCharts();
  }

  // ---------------- data load ----------------
  async loadAll() {
    const payload = await this.orm.call("waste.service.request", "get_dashboard_payload", [this.state.filters]);

    // KPIs + base
    this.state.kpis = payload?.kpis || this.state.kpis;
    this.state.busy = payload?.busy || { vehicles: [], drivers: [], assistants: [] };
    this.state.todays = this._arr(payload?.todays || payload?.today_schedule);

    // charts datasets
    this._statusGroups = this._arr(payload?.by_status);
    this._serviceGroups = this._arr(payload?.by_service);

    this._topCustomers = this._arr(payload?.top_customers || payload?.topCustomers);
    this._tankSeries = this._arr(payload?.tank_series || payload?.tankSeries);

    this._assignmentPie = payload?.assignment_pie || { labels: [], values: [] };
    this._usersPie = payload?.users_pie || { labels: [], values: [] };

    this._customerByService = this._arr(payload?.customer_by_service || payload?.customerByService);
    this._driverTrips = this._arr(payload?.driver_by_trips || payload?.driverByTrips);
    this._revenueAnalysis = this._arr(payload?.revenue_analysis || payload?.revenueAnalysis);

    // IMPORTANT:
    // - chart bin data: payload.bin_report (chart) OR payload.bin_report_chart
    this._binReportChart = this._arr(payload?.bin_report || payload?.bin_report_chart || payload?.binReport);

    this._soByCustomer = this._arr(payload?.so_by_customer || payload?.soByCustomer);

    // summary tables (XML loops)
    this.state.manifest_summary = this._arr(payload?.manifest_summary || payload?.manifests);
    this.state.so_invoice_totals = this._arr(payload?.so_invoice_totals || payload?.so_invoice_map || payload?.so_invoice_totals);
    this.state.bin_report = this._arr(payload?.bin_report_table || payload?.bin_report_rows || payload?.bin_dropped);
  }

  // ---------------- charts ----------------
  renderCharts() {
    const Chart = window.Chart;
    if (!Chart) return;

    this._destroyCharts([
      "statusChart",
      "serviceChart",
      "topCustomersChart",
      "tankChart",
      "assignmentPieChart",
      "usersPieChart",
      "customerServiceChart",
      "driverTripsChart",
      "revenueChart",
      "binChart",
      "soCustomerChart",
    ]);

    // 1) Requests by Status
    const c1 = this._ctx(this.statusCanvas);
    if (c1) {
      const labels = this._arr(this._statusGroups).map((g) => g.state || "None");
      const values = this._arr(this._statusGroups).map((g) => g.__count || 0);
      this.state.statusChart = new Chart(c1, {
        type: "bar",
        data: { labels, datasets: [{ label: "Requests", data: values }] },
        options: { responsive: true, maintainAspectRatio: false },
      });
    }

    // 2) Requests by Service
    const c2 = this._ctx(this.serviceCanvas);
    if (c2) {
      const labels = this._arr(this._serviceGroups).map((g) =>
        g.service_requested_id ? g.service_requested_id[1] : "None"
      );
      const values = this._arr(this._serviceGroups).map((g) => g.__count || 0);
      this.state.serviceChart = new Chart(c2, {
        type: "doughnut",
        data: { labels, datasets: [{ label: "Requests", data: values }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "right" } } },
      });
    }

    // 3) Top Customers
    const c3 = this._ctx(this.topCustomersCanvas);
    if (c3) {
      const rows = this._arr(this._topCustomers).slice(0, 10);
      const labels = rows.map((g) => (g.partner_id ? g.partner_id[1] : g.customer || "Unknown"));
      const values = rows.map((g) => g.__count || g.count || 0);
      this.state.topCustomersChart = new Chart(c3, {
        type: "bar",
        data: { labels, datasets: [{ label: "Requests", data: values }] },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: "y" },
      });
    }

    // 4) Tank kL series
    const c4 = this._ctx(this.tankCanvas);
    if (c4) {
      const labels = this._arr(this._tankSeries).map((x) => x.label || "Unknown");
      const values = this._arr(this._tankSeries).map((x) => x.kl || 0);
      this.state.tankChart = new Chart(c4, {
        type: "line",
        data: { labels, datasets: [{ label: "kL", data: values }] },
        options: { responsive: true, maintainAspectRatio: false },
      });
    }

    // 5) Today Jobs pie
    const c5 = this._ctx(this.assignmentPieCanvas);
    if (c5) {
      const labels = this._assignmentPie?.labels || [];
      const values = this._assignmentPie?.values || [];
      this.state.assignmentPieChart = new Chart(c5, {
        type: "pie",
        data: { labels, datasets: [{ data: values }] },
        options: { responsive: true, maintainAspectRatio: false },
      });
    }

    // 6) Users pie
    const c6 = this._ctx(this.usersPieCanvas);
    if (c6) {
      const labels = this._usersPie?.labels || [];
      const values = this._usersPie?.values || [];
      this.state.usersPieChart = new Chart(c6, {
        type: "pie",
        data: { labels, datasets: [{ data: values }] },
        options: { responsive: true, maintainAspectRatio: false },
      });
    }

    // 7) Customer by Service Offering
    const c7 = this._ctx(this.customerServiceCanvas);
    if (c7) {
      const rows = this._arr(this._customerByService).slice(0, 12);
      const labels = rows.map((r) => `${r.customer || "Unknown"} - ${r.service || "Unknown"}`);
      const values = rows.map((r) => r.count || 0);
      this.state.customerServiceChart = new Chart(c7, {
        type: "bar",
        data: { labels, datasets: [{ label: "Trips", data: values }] },
        options: { responsive: true, maintainAspectRatio: false },
      });
    }

    // 8) Driver by Trips
    const c8 = this._ctx(this.driverTripsCanvas);
    if (c8) {
      const rows = this._arr(this._driverTrips).slice(0, 12);
      const labels = rows.map((r) => r.driver || "Unknown");
      const values = rows.map((r) => r.trips || 0);
      this.state.driverTripsChart = new Chart(c8, {
        type: "bar",
        data: { labels, datasets: [{ label: "Trips", data: values }] },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: "y" },
      });
    }

    // 9) Revenue analysis
    const c9 = this._ctx(this.revenueCanvas);
    if (c9) {
      const rows = this._arr(this._revenueAnalysis);
      const labels = rows.map((r) => r.label || "");
      const values = rows.map((r) => r.amount || 0);
      this.state.revenueChart = new Chart(c9, {
        type: "line",
        data: { labels, datasets: [{ label: "Revenue", data: values }] },
        options: { responsive: true, maintainAspectRatio: false },
      });
    }

    // 10) Bin report (chart)
    const c10 = this._ctx(this.binCanvas);
    if (c10) {
      const rows = this._arr(this._binReportChart);
      const labels = rows.map((r) => r.label || "Bins");
      const values = rows.map((r) => r.count || 0);
      this.state.binChart = new Chart(c10, {
        type: "bar",
        data: { labels, datasets: [{ label: "Count", data: values }] },
        options: { responsive: true, maintainAspectRatio: false },
      });
    }

    // 11) Sales Orders by Customer
    const c11 = this._ctx(this.soCustomerCanvas);
    if (c11) {
      const rows = this._arr(this._soByCustomer).slice(0, 12);
      const labels = rows.map((r) => r.customer || "Unknown");
      const values = rows.map((r) => r.count || 0);
      this.state.soCustomerChart = new Chart(c11, {
        type: "bar",
        data: { labels, datasets: [{ label: "Sales Orders", data: values }] },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: "y" },
      });
    }
  }

  // ---------------- navigation helpers ----------------
  openRequests(domain, title) {
    this.action.doAction({
      type: "ir.actions.act_window",
      name: title || "Waste Requests",
      res_model: "waste.service.request",
      views: [
        [false, "list"],
        [false, "form"],
      ],
      domain: domain || [],
      target: "current",
    });
  }

  openTodayRow(rec) {
    this.action.doAction({
      type: "ir.actions.act_window",
      name: rec.name || "Waste Request",
      res_model: "waste.service.request",
      res_id: rec.id,
      views: [[false, "form"]],
      target: "current",
    });
  }

  openManifestListAction() {
    this.openRequests([], "Manifests");
  }

  openManifestRow(row) {
    const id = row?.id || (Array.isArray(row?.request_id) ? row.request_id[0] : false);
    if (!id) return;
    this.action.doAction({
      type: "ir.actions.act_window",
      name: row?.name || "Manifest",
      res_model: "waste.service.request",
      res_id: id,
      views: [[false, "form"]],
      target: "current",
    });
  }

  openInvoiceTotalsListAction() {
    this.action.doAction({
      type: "ir.actions.act_window",
      name: "Invoices",
      res_model: "account.move",
      views: [
        [false, "list"],
        [false, "form"],
      ],
      domain: [["move_type", "in", ["out_invoice", "out_refund"]]],
      target: "current",
    });
  }

  openInvoiceTotalsRow(row) {
    // handle invoice_id = [id,name] OR move_id OR id
    const inv = row?.invoice_id;
    const id =
      (Array.isArray(inv) && inv[0]) ||
      row?.move_id ||
      row?.invoice_id_id ||
      row?.id ||
      false;
    if (!id) return;

    this.action.doAction({
      type: "ir.actions.act_window",
      name: (Array.isArray(inv) && inv[1]) || row?.invoice || "Invoice",
      res_model: "account.move",
      res_id: id,
      views: [[false, "form"]],
      target: "current",
    });
  }

  openBinReportListAction() {
    this.openRequests([], "Bin Report");
  }

  openBinReportRow(row) {
    if (row?.request_id && Array.isArray(row.request_id)) {
      this.openManifestRow({ id: row.request_id[0], name: row.request_id[1] });
      return;
    }
    if (row?.id) this.openManifestRow(row);
  }
}

registry.category("actions").add("waste_management_zakheni.waste_dashboard", WasteDashboard);

