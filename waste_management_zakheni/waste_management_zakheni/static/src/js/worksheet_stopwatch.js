/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

function formatElapsed(totalMs) {
    const totalSec = Math.max(0, Math.floor(totalMs / 1000));
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

function toMillis(value) {
    if (!value) {
        return null;
    }
    if (typeof value.toMillis === "function") {
        return value.toMillis();
    }
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? null : parsed;
}

export class WorksheetStopwatchWidget extends Component {
    static template = "waste_management_zakheni.WorksheetStopwatch";
    static props = { ...standardWidgetProps };

    setup() {
        this.state = useState({
            elapsed: "00:00:00",
            running: false,
        });
        this._timer = null;

        onMounted(() => {
            this._tick();
            this._timer = setInterval(() => this._tick(), 1000);
        });

        onWillUnmount(() => {
            if (this._timer) {
                clearInterval(this._timer);
            }
        });
    }

    _tick() {
        const data = this.props.record.data;
        const startMs = toMillis(data.work_started_at);
        if (!startMs) {
            this.state.elapsed = "00:00:00";
            this.state.running = false;
            return;
        }

        const finishedMs = toMillis(data.work_finished_at);
        const isRunning = data.state === "in_progress" && !finishedMs;
        const endMs = finishedMs || Date.now();

        this.state.elapsed = formatElapsed(endMs - startMs);
        this.state.running = isRunning;

        if (!isRunning && this._timer) {
            clearInterval(this._timer);
            this._timer = null;
        }
    }
}

registry.category("view_widgets").add("wmz_worksheet_stopwatch", {
    component: WorksheetStopwatchWidget,
});
