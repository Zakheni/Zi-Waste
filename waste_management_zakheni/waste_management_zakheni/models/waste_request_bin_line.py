from odoo import models, fields


class WasteRequestBinLine(models.Model):
    _name = "waste.request.bin.line"
    _description = "Waste Request Pickup / Bin Mapping Line"

    request_id = fields.Many2one(
        "waste.service.request",
        string="Service Request",
        required=True,
        ondelete="cascade",
        index=True,
    )

    pickup_point_id = fields.Many2one(
        "pickup.point",
        string="Pickup Point",
        required=True,
    )

    dropoff_point_id = fields.Many2one(
        "pickup.point",
        string="Drop-off Point",
    )

    bin_lifted_ids = fields.Many2many(
        "waste.container",
        "waste_request_bin_line_lifted_rel",
        "line_id",
        "container_id",
        string="Bin Lifted",
    )

    bin_dropped_ids = fields.Many2many(
        "waste.container",
        "waste_request_bin_line_dropped_rel",
        "line_id",
        "container_id",
        string="Bin Dropped",
    )

    tank_ids = fields.Many2many(
        "waste.container",
        "waste_request_tank_line_collect_rel",
        "line_id",
        "container_id",
        string="Tank",
    )

    liters_collected = fields.Float(string="Liters Collected")
    liters_remaining = fields.Float(string="Liters Remaining")



