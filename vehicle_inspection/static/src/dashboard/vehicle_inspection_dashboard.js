/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Chart } from "@web/core/chart/chart";
console.log("🚀 Vehicle Inspection Dashboard JS LOADED");

export class VehicleInspectionDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.barChartRef = useRef("barChart");
        this.pieChartRef = useRef("pieChart");

        this.state = useState({
            total: 0,
            draft: 0,
            done: 0,
            with_faults: 0,
        });

        onWillStart(async () => {
            const data = await this.orm.call(
                "vehicle.inspection.dashboard",
                "get_dashboard_data",
                []
            );
            Object.assign(this.state, data);
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    renderCharts() {
        new Chart(this.barChartRef.el, {
            type: "bar",
            data: {
                labels: ["Draft", "Done"],
                datasets: [{
                    label: "Inspections",
                    data: [this.state.draft, this.state.done],
                    backgroundColor: ["#f39c12", "#27ae60"],
                }],
            },
        });

        new Chart(this.pieChartRef.el, {
            type: "doughnut",
            data: {
                labels: ["With Faults", "Clean"],
                datasets: [{
                    data: [
                        this.state.with_faults,
                        this.state.total - this.state.with_faults,
                    ],
                    backgroundColor: ["#e74c3c", "#2ecc71"],
                }],
            },
        });
    }

    newInspection() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "vehicle.inspection",
            view_mode: "form",
            target: "current",
        });
    }

    openMissingPhotos() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Missing Photos",
            res_model: "vehicle.inspection.line",
            view_mode: "tree,form",
            domain: [
                ["item_id.require_photo", "=", true],
                ["photo_ids", "=", false],
            ],
        });
    }
}

VehicleInspectionDashboard.template =
    "vehicle_inspection.VehicleInspectionDashboard";

registry.category("actions").add(
    "vehicle_inspection_dashboard",
    VehicleInspectionDashboard
);
