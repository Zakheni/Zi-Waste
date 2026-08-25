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
      activeSection: "overview",
      filtersOpen: false,
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
      companies: [],

      mode: { show_bins: true, show_tanks: true },
      visibility: {
        todays: false,
        statusChart: false,
        serviceChart: false,
        topCustomersChart: false,
        driverTripsChart: false,
        assignmentPieChart: false,
        manifestSummary: false,
        revenueChart: false,
        revenueCompanyChart: false,
        soInvoiceTotals: false,
        financeBanner: false,
        tankChart: false,
        binChart: false,
        binRevenueChart: false,
        binReport: false,
      },
    });

    // ---------------- Refs ----------------
    this.statusCanvas = useRef("statusCanvas");
    this.serviceCanvas = useRef("serviceCanvas");
    this.topCustomersCanvas = useRef("topCustomersCanvas");
    this.tankCanvas = useRef("tankCanvas");
    this.assignmentPieCanvas = useRef("assignmentPieCanvas");
    this.driverTripsCanvas = useRef("driverTripsCanvas");
    this.revenueCanvas = useRef("revenueCanvas");
    this.binCanvas = useRef("binCanvas");
    this.binRevenueCanvas = useRef("binRevenueCanvas");
    this.revenueCompanyCanvas = useRef("revenueCompanyCanvas");


    // ---------------- Datasets ----------------
    this._statusGroups = [];
    this._serviceGroups = [];
    this._topCustomers = [];
    this._tankSeries = [];
    this._assignmentPie = { labels: [], values: [] };
    this._driverTrips = [];
    this._revenueByCustomer = [];
    this._tankByCustomer = [];
    this._revenueByCompany = [];
    this._binReportChart = [];
    this._binRevenueChart = [];
    this._chartInstances = {};
    this.onRefresh = () => this.refreshAndRender();
    this.onTankDay = () => this.setTankGranularity("day");
    this.onTankWeek = () => this.setTankGranularity("week");
    this.onApplyFilters = () => this.refreshAndRender();
    this.onClearFilters = () => this.clearFilters();
    this.toggleFilters = () => {
      this.state.filtersOpen = !this.state.filtersOpen;
    };
    this.setSection = async (section) => {
      this.state.activeSection = section;
      await this._renderChartsWhenReady();
    };
    this.setDatePreset = (preset) => {
      const today = new Date();
      const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate());
      const fmt = (d) => d.toISOString().slice(0, 10);
      if (preset === "today") {
        this.state.filters.date_from = fmt(startOfDay);
        this.state.filters.date_to = fmt(startOfDay);
      } else if (preset === "month") {
        const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
        this.state.filters.date_from = fmt(monthStart);
        this.state.filters.date_to = fmt(startOfDay);
      } else if (preset === "30d") {
        const past = new Date(startOfDay);
        past.setDate(past.getDate() - 30);
        this.state.filters.date_from = fmt(past);
        this.state.filters.date_to = fmt(startOfDay);
      }
      this.refreshAndRender();
    };

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
        [["state", "in", ["draft", "generated", "scheduled", "dispatched", "service_delivered"]]],
        "Open Requests"
      );

    this.openScheduledClick = () => this.openRequestsFiltered([["state", "=", "scheduled"]], "Scheduled");
    this.openInProgressClick = () =>
      this.openRequestsFiltered([["state", "in", ["dispatched", "service_delivered"]]], "In Progress");
    this.openDoneClick = () => this.openRequestsFiltered([["state", "=", "done"]], "Authorised");
    this.openRejectedClick = () => this.openRequestsFiltered([["state", "=", "cancelled"]], "Rejected / Flagged");

    this.openTodayListClick = () =>
      this.openRequestsFiltered([["state", "in", ["scheduled", "dispatched"]]], "Today Schedule");
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
      try {
        await this.loadAll();
      } catch (error) {
        console.error("Waste dashboard: failed to load data", error);
      } finally {
        this.state.loading = false;
      }
    });

    onMounted(async () => {
      await this._renderChartsWhenReady();
    });
  }

  _applyKpis(kpis) {
    if (!kpis) {
      return;
    }
    Object.assign(this.state.kpis, {
      open_requests: Number(kpis.open_requests) || 0,
      scheduled_count: Number(kpis.scheduled_count) || 0,
      in_progress: Number(kpis.in_progress) || 0,
      done_count: Number(kpis.done_count) || 0,
      rejected_count: Number(kpis.rejected_count) || 0,
      tank_kl_month: Number(kpis.tank_kl_month) || 0,
      billing_amount_month: Number(kpis.billing_amount_month) || 0,
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
    await new Promise((r) => requestAnimationFrame(r));
  }

  async _renderChartsWhenReady(maxAttempts = 10) {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      await this.afterPaint();
      if (this._renderChartsForActiveSection()) {
        return;
      }
    }
  }

  _chartsReadyForSection() {
    const vis = this.state.visibility || {};
    const section = this.state.activeSection;
    const needsCanvas = [];

    if (section === "overview") {
      if (vis.statusChart) needsCanvas.push(this.statusCanvas);
      if (vis.serviceChart) needsCanvas.push(this.serviceCanvas);
      if (vis.topCustomersChart) needsCanvas.push(this.topCustomersCanvas);
    } else if (section === "operations") {
      if (vis.driverTripsChart) needsCanvas.push(this.driverTripsCanvas);
      if (vis.assignmentPieChart) needsCanvas.push(this.assignmentPieCanvas);
    } else if (section === "finance") {
      if (vis.revenueChart) needsCanvas.push(this.revenueCanvas);
      if (vis.revenueCompanyChart) needsCanvas.push(this.revenueCompanyCanvas);
    } else if (section === "assets") {
      if (this.state.mode?.show_tanks && vis.tankChart) needsCanvas.push(this.tankCanvas);
      if (this.state.mode?.show_bins && vis.binChart) needsCanvas.push(this.binCanvas);
      if (this.state.mode?.show_bins && vis.binRevenueChart) needsCanvas.push(this.binRevenueCanvas);
    }

    if (!needsCanvas.length) {
      return true;
    }
    return needsCanvas.every((ref) => ref.el);
  }

  _renderChartsForActiveSection() {
    if (!this._chartsReadyForSection()) {
      return false;
    }
    this.renderCharts();
    return true;
  }

  _destroyCharts(keys) {
    keys.forEach((k) => {
      if (this._chartInstances[k]) {
        try {
          this._chartInstances[k].destroy();
        } catch (e) {}
      }
      this._chartInstances[k] = null;
    });
  }

  async setTankGranularity(g) {
    this.state.filters.tank_granularity = g;
    await this.refreshAndRender();
  }

  async clearFilters() {
    this.state.filters.date_from = false;
    this.state.filters.date_to = false;
    this.state.filters.company_id = false;
    this.state.filters.partner_id = false;
    this.state.filters.manifest_id = false;
    this.state.filters.manifest_number = "";
    this.state.filters.sale_order_number = "";
    this.state.filters.invoice_number = "";
    await this.refreshAndRender();
  }

  async refreshAndRender() {
    this.state.loading = true;
    await this.afterPaint();

    try {
      await this.loadAll();
    } catch (error) {
      console.error("Waste dashboard: failed to refresh data", error);
    } finally {
      this.state.loading = false;
      await this._renderChartsWhenReady();
    }
  }

  async loadAll() {
    const filters = this._getSanitizedFilters();
    const payload = await this.orm.call("waste.service.request", "get_dashboard_payload", [filters]);

    this._applyKpis(payload?.kpis);
    this.state.todays = this._arr(payload?.todays);

    // datasets for charts
    this._statusGroups = this._arr(payload?.by_status);
    this._serviceGroups = this._arr(payload?.by_service);
    this._topCustomers = this._arr(payload?.top_customers);
    this._tankSeries = this._arr(payload?.tank_series);
    this._assignmentPie = payload?.assignment_pie || { labels: [], values: [] };
    this._driverTrips = this._arr(payload?.driver_by_trips);
    this._binReportChart = this._arr(payload?.bin_report_chart || payload?.bin_report);
    this._binRevenueChart = this._arr(payload?.bin_revenue_chart);
    this._revenueByCustomer = this._arr(payload?.revenue_by_customer);
    this._tankByCustomer = this._arr(payload?.tank_by_customer);
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

    this._updateVisibility();
  }

  _hasRows(rows) {
    return this._arr(rows).length > 0;
  }

  _groupCount(row) {
    if (!row) {
      return 0;
    }
    if (row.__count != null) {
      return Number(row.__count) || 0;
    }
    for (const [key, value] of Object.entries(row)) {
      if (key.endsWith("_count") && key !== "__count") {
        return Number(value) || 0;
      }
    }
    return 0;
  }

  _hasNumericData(rows, fields) {
    return this._arr(rows).some((row) =>
      fields.some((field) => {
        const value = row[field];
        return value !== undefined && value !== null && value !== "" && Number(value) !== 0;
      })
    );
  }

  _hasGroupData(rows) {
    return this._arr(rows).some((row) => this._groupCount(row) > 0);
  }

  _pieHasData(pie) {
    return (pie?.values || []).some((value) => Number(value || 0) !== 0);
  }

  _updateVisibility() {
    const kpis = this.state.kpis || {};
    Object.assign(this.state.visibility, {
      todays: this._hasRows(this.state.todays),
      statusChart: this._hasGroupData(this._statusGroups),
      serviceChart: this._hasGroupData(this._serviceGroups),
      topCustomersChart: this._hasGroupData(this._topCustomers),
      driverTripsChart: this._hasNumericData(this._driverTrips, ["trips"]),
      assignmentPieChart: this._pieHasData(this._assignmentPie),
      manifestSummary: this._hasRows(this.state.manifest_summary),
      revenueChart: this._hasNumericData(this._revenueByCustomer, ["amount"]),
      revenueCompanyChart: this._hasNumericData(this._revenueByCompany, ["amount"]),
      soInvoiceTotals: this._hasRows(this.state.so_invoice_totals),
      financeBanner:
        Number(kpis.billing_amount_month || 0) !== 0 ||
        Number(kpis.tank_kl_month || 0) !== 0 ||
        this._hasRows(this.state.so_invoice_totals) ||
        this._hasNumericData(this._revenueByCustomer, ["amount"]) ||
        this._hasNumericData(this._revenueByCompany, ["amount"]),
      tankChart: this._hasNumericData(this._tankByCustomer, ["kl"]),
      binChart: this._hasNumericData(this._binReportChart, ["count"]),
      binRevenueChart: this._hasNumericData(this._binRevenueChart, ["amount", "revenue"]),
      binReport: this._hasRows(this.state.bin_report),
    });
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
  _chartColors(n) {
    return Array.from({ length: n }, (_, i) => ({
      bg: `hsla(${(i * 47) % 360}, 70%, 58%, 0.35)`,
      bd: `hsla(${(i * 47) % 360}, 70%, 42%, 1)`,
    }));
  }

  _baseChartOptions(extra = {}) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: true } },
      ...extra,
    };
  }

  renderCharts() {
    const Chart = window.Chart;
    if (!Chart) return;

    this._destroyCharts([
      "statusChart",
      "serviceChart",
      "topCustomersChart",
      "tankChart",
      "assignmentPieChart",
      "driverTripsChart",
      "revenueChart",
      "binChart",
      "binRevenueChart",
      "revenueCompanyChart",
    ]);

    const section = this.state.activeSection;

    if (section === "overview") {
      this._renderOverviewCharts(Chart);
    } else if (section === "operations") {
      this._renderOperationsCharts(Chart);
    } else if (section === "finance") {
      this._renderFinanceCharts(Chart);
    } else if (section === "assets") {
      this._renderAssetsCharts(Chart);
    }
  }

  _renderOverviewCharts(Chart) {
    const vis = this.state.visibility || {};

    if (vis.statusChart) {
      const c1 = this._ctx(this.statusCanvas);
      if (c1) {
        const rows = this._arr(this._statusGroups);
        const labels = rows.map((g) => g.state || "None");
        const values = rows.map((g) => this._groupCount(g));
        const colors = this._chartColors(labels.length);
        this._chartInstances.statusChart = new Chart(c1, {
          type: "bar",
          data: {
            labels,
            datasets: [{
              label: "Manifests",
              data: values,
              backgroundColor: colors.map((c) => c.bg),
              borderColor: colors.map((c) => c.bd),
              borderWidth: 1,
              borderRadius: 6,
            }],
          },
          options: this._baseChartOptions({
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { grid: { display: false } } },
          }),
        });
      }
    }

    if (vis.serviceChart) {
      const c2 = this._ctx(this.serviceCanvas);
      if (c2) {
        const rows = this._arr(this._serviceGroups);
        const labels = rows.map((g) => (g.service_requested_id ? g.service_requested_id[1] : "None"));
        const values = rows.map((g) => this._groupCount(g));
        const colors = this._chartColors(labels.length);
        this._chartInstances.serviceChart = new Chart(c2, {
          type: "doughnut",
          data: {
            labels,
            datasets: [{
              data: values,
              backgroundColor: colors.map((c) => c.bd),
              borderWidth: 0,
            }],
          },
          options: this._baseChartOptions({ plugins: { legend: { position: "right" } } }),
        });
      }
    }

    if (vis.topCustomersChart) {
      const c3 = this._ctx(this.topCustomersCanvas);
      if (c3) {
        const rows = this._arr(this._topCustomers).slice(0, 8);
        const labels = rows.map((g) => (g.partner_id ? g.partner_id[1] : "Unknown"));
        const values = rows.map((g) => this._groupCount(g));
        this._chartInstances.topCustomersChart = new Chart(c3, {
          type: "bar",
          data: { labels, datasets: [{ label: "Manifests", data: values, borderRadius: 6 }] },
          options: this._baseChartOptions({ indexAxis: "y", scales: { x: { beginAtZero: true } } }),
        });
      }
    }
  }

  _renderOperationsCharts(Chart) {
    const vis = this.state.visibility || {};

    if (vis.driverTripsChart) {
      const c8 = this._ctx(this.driverTripsCanvas);
      if (c8) {
        const rows = this._arr(this._driverTrips).slice(0, 10);
        const labels = rows.map((r) => r.driver || "Unknown");
        const values = rows.map((r) => r.trips || 0);
        this._chartInstances.driverTripsChart = new Chart(c8, {
          type: "bar",
          data: { labels, datasets: [{ label: "Trips", data: values, borderRadius: 6 }] },
          options: this._baseChartOptions({ indexAxis: "y", scales: { x: { beginAtZero: true } } }),
        });
      }
    }

    if (vis.assignmentPieChart) {
      const c5 = this._ctx(this.assignmentPieCanvas);
      if (c5) {
        const labels = this._assignmentPie?.labels || [];
        const values = this._assignmentPie?.values || [];
        const colors = this._chartColors(labels.length || 1);
        this._chartInstances.assignmentPieChart = new Chart(c5, {
          type: "doughnut",
          data: {
            labels,
            datasets: [{ data: values, backgroundColor: colors.map((c) => c.bd), borderWidth: 0 }],
          },
          options: this._baseChartOptions({ plugins: { legend: { position: "bottom" } } }),
        });
      }
    }
  }

  _renderFinanceCharts(Chart) {
    const vis = this.state.visibility || {};

    if (vis.revenueChart) {
      const c9 = this._ctx(this.revenueCanvas);
      if (c9) {
        const rows = this._arr(this._revenueByCustomer).slice(0, 10);
        const labels = rows.map((r) => r.customer || "Unknown");
        const values = rows.map((r) => r.amount || 0);
        this._chartInstances.revenueChart = new Chart(c9, {
          type: "bar",
          data: { labels, datasets: [{ label: "Revenue (R)", data: values, borderRadius: 6 }] },
          options: this._baseChartOptions({
            indexAxis: "y",
            scales: { x: { beginAtZero: true, ticks: { callback: (v) => "R " + Number(v).toLocaleString() } } },
          }),
        });
      }
    }

    if (vis.revenueCompanyChart) {
      const c9b = this._ctx(this.revenueCompanyCanvas);
      if (c9b) {
        const rows = this._arr(this._revenueByCompany).slice(0, 10);
        const labels = rows.map((r) => r.company || "Unknown");
        const values = rows.map((r) => r.amount || 0);
        const colors = this._chartColors(labels.length);
        this._chartInstances.revenueCompanyChart = new Chart(c9b, {
          type: "bar",
          data: {
            labels,
            datasets: [{
              label: "Revenue (R)",
              data: values,
              backgroundColor: colors.map((c) => c.bg),
              borderColor: colors.map((c) => c.bd),
              borderWidth: 1,
              borderRadius: 6,
            }],
          },
          options: this._baseChartOptions({
            indexAxis: "y",
            scales: { x: { beginAtZero: true, ticks: { callback: (v) => "R " + Number(v).toLocaleString() } } },
          }),
        });
      }
    }
  }

  _renderAssetsCharts(Chart) {
    const vis = this.state.visibility || {};
    const showTanks = !!this.state.mode?.show_tanks;
    const showBins = !!this.state.mode?.show_bins;

    if (showTanks && vis.tankChart) {
      const c4 = this._ctx(this.tankCanvas);
      if (c4) {
        const rows = this._arr(this._tankByCustomer).slice(0, 10);
        const labels = rows.map((x) => x.customer || "Unknown");
        const values = rows.map((x) => x.kl || 0);
        this._chartInstances.tankChart = new Chart(c4, {
          type: "bar",
          data: { labels, datasets: [{ label: "kL", data: values, borderRadius: 6 }] },
          options: this._baseChartOptions({ indexAxis: "y", scales: { x: { beginAtZero: true } } }),
        });
      }
    }

    if (showBins && vis.binChart) {
      const c10 = this._ctx(this.binCanvas);
      if (c10) {
        const rows = this._arr(this._binReportChart);
        const labels = rows.map((r) => r.label || "Bins");
        const values = rows.map((r) => r.count || 0);
        this._chartInstances.binChart = new Chart(c10, {
          type: "bar",
          data: { labels, datasets: [{ label: "Count", data: values, borderRadius: 6 }] },
          options: this._baseChartOptions({ scales: { y: { beginAtZero: true } } }),
        });
      }
    }

    if (showBins && vis.binRevenueChart) {
      const c12 = this._ctx(this.binRevenueCanvas);
      if (c12) {
        const rows = this._arr(this._binRevenueChart).slice(0, 10);
        const labels = rows.map((r) => r.label || "Bin");
        const values = rows.map((r) => Number(r.amount ?? r.revenue ?? 0));
        this._chartInstances.binRevenueChart = new Chart(c12, {
          type: "bar",
          data: { labels, datasets: [{ label: "Revenue (R)", data: values, borderRadius: 6 }] },
          options: this._baseChartOptions({
            indexAxis: "y",
            scales: { x: { beginAtZero: true } },
            onClick: (_evt, elements) => {
              if (!elements?.length) return;
              const row = rows[elements[0].index];
              if (row?.bin_id) this.openBinRevenueClick(row);
            },
          }),
        });
      }
    }
  }
}

registry.category("actions").add("waste_management_zakheni.waste_dashboard", WasteDashboard);

