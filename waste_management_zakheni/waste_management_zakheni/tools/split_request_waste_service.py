"""One-off script to split request_waste_service.py into mixin modules."""
from pathlib import Path

base = Path(__file__).resolve().parent.parent / "models"
src = (base / "request_waste_service.py").read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)

WORKFLOW_START, WORKFLOW_END = 1708, 2257
ACTIONS_START, ACTIONS_END = 2258, 2867
DASHBOARD_START, DASHBOARD_END = 2869, 3846
DEAD_DOMAIN_START, DEAD_DOMAIN_END = 3072, 3145

field_blocks = [
    (2305, 2313), (2357, 2394), (2441, 2449), (2527, 2542),
    (2735, 2758), (2823, 2826), (3848, 3852),
]

skip_ranges = [
    (WORKFLOW_START, WORKFLOW_END),
    (ACTIONS_START, ACTIONS_END),
    (DASHBOARD_START, DASHBOARD_END),
]


def should_skip(lineno):
    for s, e in skip_ranges:
        if s <= lineno <= e:
            if (s, e) == (ACTIONS_START, ACTIONS_END):
                for fs, fe in field_blocks:
                    if fs <= lineno <= fe:
                        return False
            return True
    return False


main_lines = []
for i, line in enumerate(lines, start=1):
    if i <= 1707:
        main_lines.append(line)
    elif not should_skip(i):
        if i >= 3848:
            main_lines.append(line)

workflow_lines = []
for i, line in enumerate(lines, start=1):
    if WORKFLOW_START <= i <= WORKFLOW_END:
        if 1738 <= i <= 1839 and line.strip().startswith('#'):
            continue
        workflow_lines.append(line)

actions_lines = []
for i, line in enumerate(lines, start=1):
    if ACTIONS_START <= i <= ACTIONS_END:
        if any(fs <= i <= fe for fs, fe in field_blocks):
            continue
        actions_lines.append(line)

dashboard_lines = []
for i, line in enumerate(lines, start=1):
    if DASHBOARD_START <= i <= DASHBOARD_END:
        if DEAD_DOMAIN_START <= i <= DEAD_DOMAIN_END:
            continue
        dashboard_lines.append(line)

workflow_header = (
    '"""Workflow state transitions and container authorisation for waste manifests."""\n\n'
    'from odoo import models, fields, api, _\n'
    'from odoo.exceptions import UserError\n\n\n'
    'class WasteServiceRequestWorkflow(models.Model):\n'
    '    """Mixin: manifest lifecycle actions and container side-effects on authorise."""\n\n'
    "    _inherit = 'waste.service.request'\n\n"
)

actions_header = (
    '"""Document, worksheet, bin, and sales UI actions for waste manifests."""\n\n'
    'from odoo import models, fields, api, _\n'
    'from odoo.exceptions import UserError\n\n\n'
    'class WasteServiceRequestActions(models.Model):\n'
    '    """Mixin: smart buttons, wizards, and document popups."""\n\n'
    "    _inherit = 'waste.service.request'\n\n"
)

dashboard_header = (
    '"""Backend dashboard KPIs, charts, filters, and export for waste manifests."""\n\n'
    'import json\n'
    'import urllib.parse\n'
    'from datetime import datetime\n\n'
    'from odoo import models, fields, api, _\n\n\n'
    'class WasteServiceRequestDashboard(models.Model):\n'
    '    """Mixin: OWL dashboard data API and report/export actions."""\n\n'
    "    _inherit = 'waste.service.request'\n\n"
)

(base / "request_waste_service_workflow.py").write_text(
    workflow_header + ''.join(workflow_lines), encoding="utf-8")
(base / "request_waste_service_actions.py").write_text(
    actions_header + ''.join(actions_lines), encoding="utf-8")
(base / "request_waste_service_dashboard.py").write_text(
    dashboard_header + ''.join(dashboard_lines), encoding="utf-8")
(base / "request_waste_service.py").write_text(''.join(main_lines), encoding="utf-8")

print("Main:", len(main_lines))
print("Workflow:", len(workflow_lines))
print("Actions:", len(actions_lines))
print("Dashboard:", len(dashboard_lines))
