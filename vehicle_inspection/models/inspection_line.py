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
        # required=True,
    )

    # ADD IT HERE
    photo_button = fields.Char(
        string="Action",
        default=" "
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

    photo_count = fields.Integer(
        compute="_compute_photo_count",
        string="Photos"
    )

    @api.depends('photo_ids')
    def _compute_photo_count(self):
        for rec in self:
            rec.photo_count = len(rec.photo_ids)

    # @api.constrains('result', 'require_photo', 'photo_ids')
    # def _check_fault_photo_required(self):
    #
    #     for rec in self:
    #
    #         if rec.display_type == 'line_section':
    #             continue
    #
    #         if (
    #                 rec.result == 'fault'
    #                 and rec.require_photo
    #                 and len(rec.photo_ids) == 0
    #         ):
    #             raise ValidationError(
    #                 f"Please upload at least one photo for '{rec.item_id.name}'."
    #             )

    # @api.constrains('line_ids.result', 'line_ids.photo_ids')
    # def _check_required_photos(self):
    #
    #     for inspection in self:
    #
    #         for line in inspection.line_ids:
    #
    #             if (
    #                     line.display_type != 'line_section'
    #                     and line.result == 'fault'
    #                     and line.require_photo
    #                     and len(line.photo_ids) == 0
    #             ):
    #                 raise ValidationError(
    #                     f"Please upload at least one photo for '{line.item_id.name}'."
    #                 )

    @api.constrains('line_ids')
    def _check_required_photos(self):

        for inspection in self:

            for line in inspection.line_ids:

                if (
                        line.display_type != 'line_section'
                        and line.result == 'fault'
                        and line.require_photo
                        and not line.photo_ids
                ):
                    raise ValidationError(
                        f"Please upload at least one photo for '{line.item_id.name}'."
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

    # @api.constrains(
    #     'display_type',
    #     'item_id',
    #     'result',
    #     'photo_ids',
    #     'require_photo'
    # )
    # def _check_normal_lines(self):
    #
    #     for rec in self:
    #
    #         # Skip section rows
    #         if rec.display_type == 'line_section':
    #             continue
    #
    #         if not rec.item_id:
    #             raise ValidationError(
    #                 "Inspection item is required."
    #             )
    #
    #
    #         # PHOTO REQUIRED VALIDATION
    #         if (
    #                 rec.require_photo
    #                 and rec.result == 'fault'
    #                 and not rec.photo_ids
    #         ):
    #             raise ValidationError(
    #                 "Please upload photo(s) for: %s"
    #                 % rec.item_id.name
    #             )

    # def _open_fault_wizard(self):
    #
    #     self.ensure_one()
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Fault Notification',
    #         'res_model': 'vehicle.fault.wizard',
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'context': {
    #             'default_inspection_id': self.inspection_id.id,
    #         }
    #     }
    #
    # def action_open_photo_popup(self):
    #     self.ensure_one()
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Inspection Line',
    #         'res_model': 'vehicle.inspection.line',
    #         'view_mode': 'form',
    #         'res_id': self.id,
    #         'target': 'new',
    #     }

    # @api.constrains(
    #     'display_type',
    #     'item_id',
    #     'result',
    #     'photo_ids',
    #     'require_photo'
    # )
    # def _check_photo_required(self):
    #
    #     for rec in self:
    #
    #         if rec.display_type == 'line_section':
    #             continue
    #
    #         if not rec.item_id:
    #             raise ValidationError(
    #                 "Inspection item is required."
    #             )
    #
    #         if (
    #                 rec.require_photo
    #                 and rec.result == 'fault'
    #                 and not rec.photo_ids
    #         ):
    #             raise ValidationError(
    #                 "Photo is required for this fault."
    #             )

    # def action_open_photo_popup(self):
    #     self.ensure_one()
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Inspection Line',
    #         'res_model': 'vehicle.inspection.line',
    #         'view_mode': 'form',
    #         'res_id': self.id,
    #         'target': 'new',
    #     }

    def action_open_photo_popup(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Inspection Line',
            'res_model': 'vehicle.inspection.line',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }