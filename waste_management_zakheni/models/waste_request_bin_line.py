from odoo import models, fields


class WasteRequestBinLine(models.Model):
    _name = "waste.request.bin.line"
    _description = "Waste Request Pickup Point / Bin Mapping Line"

    request_id = fields.Many2one(
        "waste.service.request",
        string="Service Request",
        required=True,
        ondelete="cascade",
        index=True,
    )

    pickup_point_id = fields.Many2one(
        "pickup.point",
        string="Pickup / Dropoff Point",
        required=True,
    )

    # Placement / Removal / Collection
    container_ids = fields.Many2many(
        "waste.container",
        "waste_request_bin_line_cont_rel",
        "line_id",
        "container_id",
        string="Containers",
        required=True,
    )

    # Shunting
    shunt_container_ids = fields.Many2many(
        "waste.container",
        "waste_request_bin_line_shunt_rel",
        "line_id",
        "container_id",
        string="Bins to Shunt",
        required=True,
    )

    # Swapping
    lifted_container_ids = fields.Many2many(
        "waste.container",
        "waste_request_bin_line_lifted_rel",
        "line_id",
        "container_id",
        string="Lifted Bins",
        required=True,
    )
    dropped_container_ids = fields.Many2many(
        "waste.container",
        "waste_request_bin_line_dropped_rel",
        "line_id",
        "container_id",
        string="Dropped Bins",
        required=True,
    )


# from odoo import models, fields
#
# class WasteRequestBinLine(models.Model):
#     _name = 'waste.request.bin.line'
#     _description = 'Waste Request Pickup/Bin Line'
#
#     request_id = fields.Many2one(
#         'waste.service.request',
#         string="Service Request",
#         required=True,
#         ondelete='cascade',
#     )
#
#     pickup_point_id = fields.Many2one(
#         'pickup.point',
#         string="Pickup Point",
#         required=True,
#     )
#
#     container_ids = fields.Many2many(
#         'waste.container',
#         'waste_request_bin_line_container_rel',  # relation table
#         'line_id',                               # this model column
#         'container_id',                          # waste.container column
#         string="Bins",
#         help="Bins assigned to this pickup point for the request.",
#     )
