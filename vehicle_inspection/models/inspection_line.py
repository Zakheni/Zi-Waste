from odoo import models, fields, api
from odoo.exceptions import ValidationError


class VehicleInspectionLine(models.Model):
    _name = "vehicle.inspection.line"
    _description = "Vehicle Inspection Line"

    name = fields.Char()

    display_type = fields.Selection([
        ('line_section', "Section"),
    ], default=False)

    inspection_id = fields.Many2one(
        'vehicle.inspection',
        ondelete='cascade',
        required=True
    )

    item_id = fields.Many2one(
        'vehicle.inspection.item',

    )

    category_id = fields.Many2one(
        related='item_id.category_id',
        store=True
    )

    result = fields.Selection([
        ("clear", "Clear"),
        ("fault", "Fault"),
    ], )

    note = fields.Text()

    photo_ids = fields.One2many(
        'vehicle.inspection.image',
        'line_id',
        string='Photos',
        required=True,
    )

    require_photo = fields.Boolean(
        related='item_id.require_photo',
        store=True,
        readonly=True
    )

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        related='inspection_id.vehicle_id',
        store=True,
        readonly=True
    )

    def action_open_photos(self):

        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Photos',
            'res_model': 'vehicle.inspection.image',
            'view_mode': 'tree,form',
            'target': 'new',
            'domain': [('line_id', '=', self.id)],
            'context': {
                'default_line_id': self.id,
            }
        }

    _sql_constraints = [

        (
            'unique_item_per_inspection',
            'unique(inspection_id, item_id)',
            'Each inspection item can only appear once.'
        ),

    ]

    @api.constrains(
        'display_type',
        'item_id',
        'result',
        'photo_ids',
        'require_photo'
    )
    def _check_normal_lines(self):

        for rec in self:

            # Skip section rows
            if rec.display_type == 'line_section':
                continue

            if not rec.item_id:
                raise ValidationError(
                    "Inspection item is required."
                )


            # PHOTO REQUIRED VALIDATION
            if (
                    rec.require_photo
                    and rec.result == 'fault'
                    and not rec.photo_ids
            ):
                raise ValidationError(
                    "Please upload photo(s) for: %s"
                    % rec.item_id.name
                )

    # @api.model_create_multi
    # def create(self, vals_list):
    #
    #     records = super().create(vals_list)
    #
    #     records.mapped(
    #         'inspection_id'
    #     )._update_state_from_lines()
    #
    #     return records

    # def write(self, vals):
    #     res = super().write(vals)
    #
    #     self.mapped(
    #         'inspection_id'
    #     )._update_state_from_lines()
    #
    #     return res

    # def write(self, vals):
    #
    #     res = super().write(vals)
    #
    #     self.mapped(
    #         'inspection_id'
    #     )._update_state_from_lines()
    #
    #     # Trigger wizard when fault selected
    #     if vals.get('result') == 'fault':
    #         return self._open_fault_wizard()
    #
    #     return res

    # def write(self, vals):
    #
    #     res = super().write(vals)
    #
    #     self.mapped(
    #         'inspection_id'
    #     )._update_state_from_lines()
    #
    #     return res

    # @api.constrains("photo_ids", "require_photo", "result")
    # def _check_required_photo(self):
    #
    #     for line in self:
    #
    #         # Skip unsaved/new records
    #         if not line._origin.id:
    #             continue
    #
    #         if (
    #                 line.require_photo
    #                 and line.result == "fault"
    #                 and not line.photo_ids
    #         ):
    #             raise ValidationError(
    #                 "Photos are required for item: %s"
    #                 % line.item_id.name
    #             )

    def _open_fault_wizard(self):

        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Fault Notification',
            'res_model': 'vehicle.fault.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_inspection_id': self.inspection_id.id,
            }
        }

    # @api.onchange('result')
    # def _onchange_result(self):
    #
    #     if self.result == 'fault':
    #         return {
    #             'warning': {
    #                 'title': 'Fault Detected',
    #                 'message': (
    #                     'Please notify the Reporting '
    #                     'Manager.'
    #                 )
    #             }
    #         }