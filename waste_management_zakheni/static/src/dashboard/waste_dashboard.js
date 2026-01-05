/** @odoo-module **/

import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class WasteDashboard extends Component {
  static template = "waste_management_zakheni.WasteDashboard";

  _safeId(val) {
    if (!val) return false;
    if (Array.isArray(val)) {
      const id = val[0];
      return Number.isInteger(id) ? id : false;
    }
    if (Number.isInteger(val)) return val;
    if (typeof val === "string") {
      const s = val.trim();
      return /^\d+$/.test(s) ? parseInt(s, 10) : false;
    }
    return false;
  }

  _getSanitizedFilters() {
    const f = { ...(this.state.filters || {}) };
    f.partner_id = this._safeId(f.partner_id);
    f.company_id = this._safeId(f.company_id);

    // if user cleared manifest_number, also clear manifest_id
    if (!f.manifest_number) f.manifest_id = false;

    return f;
  }

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
        manifest_id: false,
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

      todays: [],
      manifest_summary: [],
      so_invoice_totals: [],
      bin_report: [],
      customers: [],
      bin_revenue_table: [],
      companies: [],   // ✅ NEW (dropdown list)


      // chart instances (we destroy/rebuild)
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
      binRevenueChart: null,
      revenueCompanyChart: null,
      mode: { show_bins: true, show_tanks: true },


    });

    // ---------------- Refs ----------------
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
    this.binRevenueCanvas = useRef("binRevenueCanvas");
    this.revenueCompanyCanvas = useRef("revenueCompanyCanvas");


    // ---------------- Datasets ----------------
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
    this._binRevenueChart = [];
    this._revenueByCustomer = [];
    this._tankByCustomer = [];
    this._revenueByCompany = [];



    // ---------------- Buttons ----------------
    this.onRefresh = () => this.refreshAndRender();
    this.onTankDay = () => this.setTankGranularity("day");
    this.onTankWeek = () => this.setTankGranularity("week");
    this.onApplyFilters = () => this.refreshAndRender();
    this.onClearFilters = () => this.clearFilters();

    this.onBinRevenueRowClick = this.onBinRevenueRowClick.bind(this);
    this.onBinRevenueViewClick = this.onBinRevenueViewClick.bind(this);
    this.openBinRevenueClick = this.openBinRevenueClick.bind(this);
    this.openBinContainer = this.openBinContainer.bind(this);

    this.onBinRevenueRowClick = (row) => this.openBinContainer(row);
    this.onBinRevenueViewClick = (ev, row) => {
      if (ev) ev.stopPropagation();
      this.openBinContainer(row);
    };
    this.openTodayRowClick = (r) => this.openTodayRow(r);




    // ---------------- Table actions ----------------
    this.openManifestList = () => this.openManifestListAction();

    // ✅ Row click = open form
    this.openManifestRowClick = (m) => this.openManifestRow(m);

    // ✅ Filter button = apply filter + reload (this affects SO↔Invoice)
    this.applyManifestFilterClick = async (m) => {
      this.state.filters = {
        ...(this.state.filters || {}),
        manifest_id: m.id,
        manifest_number: m.name || "",
      };
      await this.refreshAndRender();
    };

    this.openInvoiceTotalsList = () => this.openInvoiceTotalsListAction();
    this.openInvoiceTotalsRowClick = (row) => this.openInvoiceTotalsRow(row);

    this.openBinReportList = () => this.openBinReportListAction();
    this.openBinReportRowClick = (row) => this.openBinReportRow(row);
        // Today list + row
     this.openOpenClick = () =>
      this.openRequestsFiltered(
        [["state", "in", ["draft", "generated", "scheduled", "assigned", "dispatched", "service_delivered"]]],
        "Open Requests"
      );

    this.openScheduledClick = () => this.openRequestsFiltered([["state", "=", "scheduled"]], "Scheduled");
    this.openInProgressClick = () =>
      this.openRequestsFiltered([["state", "in", ["assigned", "dispatched", "service_delivered"]]], "In Progress");
    this.openDoneClick = () => this.openRequestsFiltered([["state", "=", "done"]], "Authorised");
    this.openRejectedClick = () => this.openRequestsFiltered([["state", "=", "cancelled"]], "Rejected / Flagged");

    this.openTodayListClick = () =>
      this.openRequestsFiltered([["state", "in", ["scheduled", "assigned", "dispatched"]]], "Today Schedule");
    this.openTodayRowClick = (rec) => this.openTodayRow(rec);


    this.onPrintPdf = () => this.printDashboard();
    this.onExportXlsx = () => this.exportDashboardXlsx();

    // ✅ PDF
    this.printDashboard = async () => {
      const filters = { ...(this.state.filters || {}) };
      filters.partner_id = this._safeId(filters.partner_id);
      filters.company_id = this._safeId(filters.company_id);

      const action = await this.orm.call(
        "waste.service.request",
        "action_print_dashboard_report",
        [filters]
      );
      this.action.doAction(action);
    };

    // ✅ Excel
    this.exportDashboardXlsx = async () => {
      const filters = { ...(this.state.filters || {}) };
      filters.partner_id = this._safeId(filters.partner_id);
      filters.company_id = this._safeId(filters.company_id);

      const action = await this.orm.call(
        "waste.service.request",
        "action_export_dashboard_xlsx",
        [filters]
      );
      this.action.doAction(action);
    };


    // ---------------- Lifecycle ----------------
    onWillStart(async () => {
      await this.ensureChartJS();
    });

    onMounted(async () => {
      await this.afterPaint();
      await this.refreshAndRender();
    });
  }

  _arr(x) {
    return Array.isArray(x) ? x : [];
  }

  _ctx(ref) {
    return ref && ref.el ? ref.el.getContext("2d") : null;
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

  async setTankGranularity(g) {
    this.state.filters.tank_granularity = g;
    await this.refreshAndRender();
  }

  async clearFilters() {
    this.state.filters.date_from = false;
    this.state.filters.date_to = false;
    this.state.filters.manifest_id = false;
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

  async loadAll() {
    const filters = this._getSanitizedFilters();
    const payload = await this.orm.call("waste.service.request", "get_dashboard_payload", [filters]);

    this.state.kpis = payload?.kpis || this.state.kpis;
    this.state.todays = this._arr(payload?.todays);

    // datasets for charts
    this._statusGroups = this._arr(payload?.by_status);
    this._serviceGroups = this._arr(payload?.by_service);
    this._topCustomers = this._arr(payload?.top_customers);
    this._tankSeries = this._arr(payload?.tank_series);
    this._assignmentPie = payload?.assignment_pie || { labels: [], values: [] };
    this._usersPie = payload?.users_pie || { labels: [], values: [] };
    this._customerByService = this._arr(payload?.customer_by_service);
    this._driverTrips = this._arr(payload?.driver_by_trips);
    this._revenueAnalysis = this._arr(payload?.revenue_analysis);
    this._binReportChart = this._arr(payload?.bin_report_chart || payload?.bin_report);
    this._soByCustomer = this._arr(payload?.so_by_customer);
    this._binRevenueChart = this._arr(payload?.bin_revenue_chart);

//    this._revenueByCustomer = this._arr(payload?.revenue_by_customer || payload?.revenueByCustomer);
    this._revenueByCustomer = this._arr(payload?.revenue_by_customer);
    this._tankByCustomer = this._arr(payload?.tank_by_customer);
//    this._revenueByCompany = this._arr(payload?.revenue_by_company);
    this._revenueByCompany = this._arr(payload?.revenue_by_company);






    // tables
    this.state.manifest_summary = this._arr(payload?.manifest_summary);
    this.state.so_invoice_totals = this._arr(payload?.so_invoice_totals);
    this.state.bin_report = this._arr(payload?.bin_report_table);
    this.state.customers = Array.isArray(payload?.customers) ? payload.customers : [];
    this.state.bin_revenue_table = this._arr(payload?.bin_revenue_table);

    this.state.companies = Array.isArray(payload?.companies) ? payload.companies : [];
    this.state.customers = Array.isArray(payload?.customers) ? payload.customers : [];
    this.state.mode = payload?.mode || { show_bins: true, show_tanks: true };





  }

  // ---------------------------------------------------------
  // Navigation helpers
  // ---------------------------------------------------------
  openRequests(domain, title) {
    this.action.doAction({
      type: "ir.actions.act_window",
      name: title || "Waste Requests",
      res_model: "waste.service.request",
      views: [[false, "list"], [false, "form"]],
      domain: domain || [],
      target: "current",
    });
  }

  async openRequestsFiltered(extraDomain, title) {
    const filters = this._getSanitizedFilters();
    const baseDomain = await this.orm.call("waste.service.request", "get_dashboard_open_domain", [filters]);
    const finalDomain = (baseDomain || []).concat(extraDomain || []);
    this.openRequests(finalDomain, title);
  }

  openManifestListAction() {
    this.openRequestsFiltered([], "Manifests");
  }

  openManifestRow(row) {
    const id = row?.id || false;
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
      views: [[false, "list"], [false, "form"]],
      domain: [["move_type", "in", ["out_invoice", "out_refund"]]],
      target: "current",
    });
  }

  openInvoiceTotalsRow(row) {
    const inv = row?.invoice_id;
    const id = (Array.isArray(inv) && inv[0]) || row?.id || false;
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
    this.openRequestsFiltered([], "Bin Report");
  }

  openBinReportRow(row) {
    // row.request_id is [id, name] in your python table
    if (row?.request_id && Array.isArray(row.request_id)) {
      this.openManifestRow({ id: row.request_id[0], name: row.request_id[1] });
      return;
    }
    if (row?.id) this.openManifestRow(row);
  }

  // If you use clickable Bin Revenue chart -> call python domain by bin id
  async openBinRevenueClick(rowOrBinId) {
    const binId = Number.isInteger(rowOrBinId)
      ? rowOrBinId
      : (rowOrBinId && rowOrBinId.bin_id) || false;

    if (!binId) return;

    const filters = this._getSanitizedFilters();
    const baseDomain = await this.orm.call("waste.service.request", "get_dashboard_open_domain", [filters]);

    const extraDomain = [
      "|",
      ["bin_lifted_ids", "in", [binId]],
      ["bin_dropped_ids", "in", [binId]],
    ];

    const finalDomain = (baseDomain || []).concat(extraDomain);
    this.openRequests(finalDomain, `Bin: ${binId}`);
  }

    // ✅ Bin Revenue TABLE: row click -> open manifests filtered by this bin
  onBinRevenueRowClick(row) {
    if (!row?.bin_id) return;
    this.openBinRevenueClick(row);
  }

  // ✅ Optional: button click (same behaviour, but stops row click conflicts in XML)
  onBinRevenueViewClick(ev, row) {
    if (ev) ev.stopPropagation();
    if (!row?.bin_id) return;
    this.openBinRevenueClick(row);
  }
// ----- container
  openBinContainer(rowOrBinId) {
  const binId = Number.isInteger(rowOrBinId)
    ? rowOrBinId
    : (rowOrBinId && rowOrBinId.bin_id) || false;

  if (!binId) return;

  // Try waste.container first, fallback to stock.lot
  this.action.doAction({
    type: "ir.actions.act_window",
    name: "Bin",
    res_model: "waste.container",
    res_id: binId,
    views: [[false, "form"]],
    target: "current",
  }).catch(() => {
    this.action.doAction({
      type: "ir.actions.act_window",
      name: "Bin",
      res_model: "stock.lot",
      res_id: binId,
      views: [[false, "form"]],
      target: "current",
    });
  });
}

openTodayRow(row) {
  const id = row?.id || false;
  if (!id) return;

  this.action.doAction({
    type: "ir.actions.act_window",
    name: row?.name || "Waste Request",
    res_model: "waste.service.request",
    res_id: id,
    views: [[false, "form"]],
    target: "current",
  });
}

// Row click handler used by XML: openTodayRowClick(r)
openTodayRowClick(row) {
  this.openTodayRow(row);
}


  // ---------------------------------------------------------
  // Charts
  // ---------------------------------------------------------
  renderCharts() {
    const Chart = window.Chart;
    if (!Chart) return;

          // ✅ Must match payload.mode from python
      const showBins = !!this.state.mode?.show_bins;
      const showTanks = !!this.state.mode?.show_tanks;

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
      "binRevenueChart",
      "revenueCompanyChart",

    ]);



//     // ✅ Revenue by Company (BAR)
//    const ctx = this._ctx(this.revenueByCompanyCanvas);
//    if (ctx) {
//      const rows = this._arr(this._revenueByCompany);
//      const labels = rows.length ? rows.map((r) => r.company || "Unknown") : ["No Data"];
//      const values = rows.length ? rows.map((r) => r.amount || 0) : [0];
//
//      this.state.revenueByCompanyChart = new Chart(ctx, {
//        type: "bar",
//        data: {
//          labels,
//          datasets: [{
//           label: "Revenue", data: values }],
//        },
//        options: {
//          responsive: true,
//          maintainAspectRatio: false,
//        },
//      });
//    }

//// ✅ Revenue by Company (BAR) — custom colors
//const ctx = this._ctx(this.revenueByCompanyCanvas);
//if (ctx) {
//  const rows = this._arr(this._revenueByCompany);
//  const labels = rows.length ? rows.map((r) => r.company || "Unknown") : ["No Data"];
//  const values = rows.length ? rows.map((r) => r.amount || 0) : [0];
//
//  this.state.revenueByCompanyChart = new Chart(ctx, {
//    type: "bar",
//    data: {
//      labels,
//      datasets: [
//        {
//          label: "Revenue",
//          data: values,
//
//          // ✅ pick your colors here
//          backgroundColor: "rgba(102, 126, 234, 0.35)", // soft purple/blue
//          borderColor: "rgba(102, 126, 234, 1)",        // solid line
//          borderWidth: 2,
//          borderRadius: 8,
//        },
//      ],
//    },
//    options: {
//      responsive: true,
//      maintainAspectRatio: false,
//      plugins: {
//        legend: { display: true },
//        tooltip: { enabled: true },
//      },
//      scales: {
//        x: {
//          grid: { display: false },
//          ticks: { maxRotation: 0, minRotation: 0 },
//        },
//        y: {
//          beginAtZero: true,
//          ticks: {
//            callback: (v) => "R " + Number(v || 0).toLocaleString(),
//          },
//        },
//      },
//    },
//  });
//}
// ✅ Revenue by Company (BAR) — very visible colors (to confirm it changed)
const cRevCo = this._ctx(this.revenueByCompanyCanvas);
if (cRevCo) {
  const rows = this._arr(this._revenueByCompany);

  const labels = rows.length ? rows.map((r) => r.company || "Unknown") : ["No Data"];
  const values = rows.length ? rows.map((r) => r.amount || 0) : [0];

  // multi-color bars (obvious)
  const bg = labels.map((_, i) => `hsla(${(i * 55) % 360}, 85%, 60%, 0.45)`);
  const bd = labels.map((_, i) => `hsla(${(i * 55) % 360}, 85%, 45%, 1)`);

  this.state.revenueByCompanyChart = new Chart(cRevCo, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Revenue by Company",
          data: values,
          backgroundColor: bg,
          borderColor: bd,
          borderWidth: 2,
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: true } },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: (v) => "R " + Number(v || 0).toLocaleString(),
          },
        },
        x: { grid: { display: false } },
      },
    },
  });
}


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
      const labels = rows.map((g) => (g.partner_id ? g.partner_id[1] : "Unknown"));
      const values = rows.map((g) => g.__count || 0);
      this.state.topCustomersChart = new Chart(c3, {
        type: "bar",
        data: { labels, datasets: [{ label: "Requests", data: values }] },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: "y" },
      });
    }


    // 4) Tank kL by Customer (BAR: Y=Customer, X=kL)
    const c4 = this._ctx(this.tankCanvas);
    if (c4) {
      const rows = this._arr(this._tankByCustomer);

      const labels = rows.length ? rows.map((x) => x.customer || "Unknown") : ["No Data"];
      const values = rows.length ? rows.map((x) => x.kl || 0) : [0];

      this.state.tankChart = new Chart(c4, {
        type: "bar",
        data: { labels, datasets: [{ label: "Tank kL", data: values }] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: "y",   // ✅ horizontal bars
        },
      });
    }


    // 5) Jobs pie
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

    // 8) Driver by Trips Traveled
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

    // 9) Revenue by Customer (BAR: Y=Customer, X=Revenue)
    const c9 = this._ctx(this.revenueCanvas);
    if (c9) {
      const rows = this._arr(this._revenueByCustomer);

      const labels = rows.length ? rows.map((r) => r.customer || "Unknown") : ["No Data"];
      const values = rows.length ? rows.map((r) => r.amount || 0) : [0];

      this.state.revenueChart = new Chart(c9, {
        type: "bar",
        data: { labels, datasets: [{ label: "Revenue", data: values }] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: "y",
        },
      });
    }

    // 9B) Revenue by Company (BAR)
    const c9b = this._ctx(this.revenueCompanyCanvas);
    if (c9b) {
      const rows = this._arr(this._revenueByCompany);
      const labels = rows.length ? rows.map((r) => r.company || "Unknown") : ["No Data"];
      const values = rows.length ? rows.map((r) => r.amount || 0) : [0];

      this.state.revenueCompanyChart = new Chart(c9b, {
        type: "bar",
        data: { labels, datasets: [{ label: "Revenue", data: values }] },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: "y" },
      });
    }

     // 9C Revenue by Company (BAR)
    const c9C  = this._ctx(this.revenueByCompanyCanvas);
    if (c9C) {
      const rows = this._arr(this._revenueByCompany);
      const labels = rows.length ? rows.map((r) => r.company || "No Company") : ["No Data"];
      const values = rows.length ? rows.map((r) => r.amount || 0) : [0];
      this.state.revenueByCompanyChart = new Chart(c9C, {
        type: "bar",
        data: { labels, datasets: [{ label: "Revenue", data: values }] },
        options: { responsive: true, maintainAspectRatio: false },
      });
    }


    // 10) Bin Report chart
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

    // 11) Sales Order by Customer
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

    // 12) Bin Revenue chart (clickable)
    const c12 = this._ctx(this.binRevenueCanvas);
    if (c12) {
      const rows = this._arr(this._binRevenueChart).slice(0, 10);
      const labels = rows.map((r) => r.label || "Bin");
      const values = rows.map((r) => r.amount || 0);

      this.state.binRevenueChart = new Chart(c12, {
        type: "bar",
        data: { labels, datasets: [{ label: "Revenue", data: values }] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: "y",
          onClick: (_evt, elements) => {
            if (!elements || !elements.length) return;
            const idx = elements[0].index;
            const row = rows[idx];
            if (row?.bin_id) this.openBinRevenueClick(row);
          },
        },
      });
    }
  }
}

registry.category("actions").add("waste_management_zakheni.waste_dashboard", WasteDashboard);

