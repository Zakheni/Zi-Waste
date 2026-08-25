/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { onMounted, onPatched } from "@odoo/owl";

function applyWorksheetKanbanLayout(rootEl) {
    if (!rootEl?.classList.contains("o_wmz_worksheet_kanban")) {
        return;
    }
    const renderer = rootEl.querySelector(".o_kanban_renderer.o_kanban_grouped");
    if (!renderer) {
        return;
    }
    renderer.style.setProperty("display", "grid", "important");
    renderer.style.setProperty("grid-template-columns", "repeat(3, minmax(0, 1fr))", "important");
    renderer.style.setProperty("width", "100%", "important");
    renderer.style.setProperty("overflow-x", "hidden", "important");
    for (const col of renderer.querySelectorAll(".o_kanban_group")) {
        col.style.setProperty("max-width", "none", "important");
        col.style.setProperty("width", "100%", "important");
        col.style.setProperty("flex", "none", "important");
    }
    const quickCreate = renderer.querySelector(".o_column_quick_create");
    if (quickCreate) {
        quickCreate.style.setProperty("display", "none", "important");
    }
}

patch(KanbanController.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => applyWorksheetKanbanLayout(this.rootRef.el));
        onPatched(() => applyWorksheetKanbanLayout(this.rootRef.el));
    },
});
