"""Dashboard data provider for vehicle inspection KPIs."""

from odoo import models


class VehicleInspectionDashboard(models.AbstractModel):
    """Abstract model exposing aggregated inspection statistics.

    Used by the backend dashboard to display counts of inspections,
    drafts, faults, and lines missing required photos.
    """

    _name = "vehicle.inspection.dashboard"
    _description = "Vehicle Inspection Dashboard"

    def get_dashboard_data(self):
        """Return summary counts for the inspection dashboard.

        Returns:
            dict: Keys total, draft, faults, and missing_photos with
                integer counts.
        """
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
