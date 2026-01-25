from odoo import models

class VehicleInspectionDashboard(models.AbstractModel):
    _name = "vehicle.inspection.dashboard"
    _description = "Vehicle Inspection Dashboard"

    def get_dashboard_data(self):
        Inspection = self.env["vehicle.inspection"]
        Line = self.env["vehicle.inspection.line"]

        return {
            "total": Inspection.search_count([]),
            "draft": Inspection.search_count([("state", "=", "draft")]),
            "faults": Inspection.search_count([("has_issue", "=", True)]),
            "missing_photos": Line.search_count([
                ("item_id.require_photo", "=", True),
                ("photo_ids", "=", False),
            ]),
        }
