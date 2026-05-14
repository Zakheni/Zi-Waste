from odoo import models, fields, api
from odoo.exceptions import ValidationError

class VehicleInspectionLine(models.Model):
    _name = "vehicle.inspection.line"
    _description = "Vehicle Inspection Line"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # inspection_id = fields.Many2one("vehicle.inspection", required=True, ondelete="cascade")
    # category_id = fields.Many2one("vehicle.inspection.category", required=True)
    # item_id = fields.Many2one("vehicle.inspection.item", required=True)
    # result = fields.Selection([
    #     ("clear", "Clear"),
    #     ("fault", "Fault"),
    #     # ("na", "N/A")
    # ], default="clear", required=True, tracking=True)
    # note = fields.Text()
    # photo_ids = fields.Many2many("ir.attachment", string="Photos")

    nane = fields.Char()

    inspection_id = fields.Many2one(
        'vehicle.inspection',
        ondelete='cascade',
        required=True, tracking=True
    )

    item_id = fields.Many2one(
        'vehicle.inspection.item',
        required=True, tracking=True
    )

    category_id = fields.Many2one(
        related='item_id.category_id',
        store=True, tracking=True
    )

    result = fields.Selection([
        ("clear", "Clear"),
        ("fault", "Fault"),
        # ("na", "N/A")
        ], default="clear", required=True, tracking=True)
    note = fields.Text()

    photo_ids = fields.One2many(
        'vehicle.inspection.image',
        'line_id',
        string='Photos', tracking=True
    )

    # ✅ THIS FIELD MUST BE HERE (AND ONLY HERE)
    require_photo = fields.Boolean(
        related='item_id.require_photo',
        store=True,
        readonly=True, tracking=True
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        related='inspection_id.vehicle_id',
        store=True,
        readonly=True, tracking=True
    )

    # @api.onchange('result')
    # def _onchange_result_photo_warning(self):
    #     if (
    #             self.item_id.require_photo
    #             and self.result == 'fault'
    #             and not self.photo_ids
    #     ):
    #         return {
    #             'warning': {
    #                 'title': 'Photo required',
    #                 'message': f"Please add photos for item: {self.item_id.name}"
    #             }
    #         }

    def open_line_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Inspection Line',
            'res_model': 'vehicle.inspection.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',  # popup
        }

    _sql_constraints = [
        (
            'unique_item_per_inspection',
            'unique(inspection_id, item_id)',
            'Each inspection item can only be used once per inspection.'
        )
    ]