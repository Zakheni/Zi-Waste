from odoo import models, fields, api
from odoo.exceptions import ValidationError


class VehicleInspection(models.Model):
    _name = "vehicle.inspection"
    _description = "Vehicle Inspection"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string='Reference',
        required=True,
        # copy=False,
        readonly=True,
        default='New',
        tracking=True)

    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True
    )

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('vehicle.inspection') or 'New'

        return super().create(vals)

    inspection_type = fields.Selection([
        ("fleet", "Internal Fleet"),
        ("customer", "Customer / Garage")
    ], default="fleet", required=True)

    vehicle_id = fields.Many2one("fleet.vehicle", required=True)
    partner_id = fields.Many2one("res.partner")
    inspection_date = fields.Date(default=fields.Date.today, required=True)
    inspector_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    driver_id = fields.Many2one("hr.employee", string="driver")
    vehicle_description = fields.Text(string="Vehicle Description")
    comment = fields.Text(string="Comment")
    km_open = fields.Float(string="KM Opening")
    km_close = fields.Float(string="KM Closing")
    line_ids = fields.One2many("vehicle.inspection.line", "inspection_id", tracking=True)
    signature = fields.Binary(string="Inspector Signature")
    next_inspection_date = fields.Date()

    has_issue = fields.Boolean(compute="_compute_has_issue", store=True)
    state = fields.Selection([("draft", "Draft"), ("done", "Done")], default="draft", tracking=True)

    item_id = fields.Many2one(
        'vehicle.inspection.item',
        required=True
    )

    # ✅ THIS FIELD MUST BE HERE (AND ONLY HERE)
    require_photo = fields.Boolean(
        related='item_id.require_photo',
        store=True,
        readonly=True
    )

    @api.depends("line_ids.result")
    def _compute_has_issue(self):
        for rec in self:
            rec.has_issue = any(l.result == "not_ok" for l in rec.line_ids)

    @api.onchange("inspection_type")
    def _onchange_inspection_type(self):
        self.line_ids = [(5, 0, 0)]
        items = self.env["vehicle.inspection.item"].search([])
        self.line_ids = [(0, 0, {
            "category_id": i.category_id.id,
            "item_id": i.id
        }) for i in items]

    def action_draft(self):
        self.state = "draft"

    def action_done(self):
        for rec in self:
            if rec.state != "draft":
                return
            if rec.has_issue and rec.vehicle_id:
                rec.vehicle_id.message_post(
                    body="⚠ Vehicle has inspection issues."
                )
            rec.state = "done"


    @api.constrains("inspection_type", "vehicle_id", "partner_id")
    def _check_inspection_target(self):
        for rec in self:
            if rec.inspection_type == "fleet" and not rec.vehicle_id:
                raise ValidationError("Fleet inspections require a vehicle.")
            if rec.inspection_type == "customer" and not rec.partner_id:
                raise ValidationError("Customer inspections require a customer.")

    def action_print_inspection_report(self):
        self.ensure_one()
        return self.env.ref(
            "vehicle_inspection.action_vehicle_inspection_report"
        ).report_action(self)

    used_item_ids = fields.Many2many(
        'vehicle.inspection.item',
        compute='_compute_used_item_ids',
        store=False,
    )

    @api.depends('line_ids.item_id')
    def _compute_used_item_ids(self):
        for rec in self:
            rec.used_item_ids = rec.line_ids.mapped('item_id')



    # image_ids = fields.One2many(
    #     'vehicle.inspection.image',
    #     'line_id',
    #     string='Photos',
    # )
    image_ids = fields.Many2many(
        'vehicle.inspection.image',
        compute='_compute_image_ids',
        string='Photos',
        store=False,
    )

    @api.depends('line_ids.photo_ids')
    def _compute_image_ids(self):
        for inspection in self:
            inspection.image_ids = inspection.line_ids.mapped('photo_ids')

    # @api.model
    # def get_dashboard_data(self):
    #     return {
    #         "total": self.search_count([]),
    #         "draft": self.search_count([("state", "=", "draft")]),
    #         "faults": self.search_count([("has_issue", "=", True)]),
    #     }

    # Dashbaord



class VehicleInspectionImage(models.Model):
    _name = 'vehicle.inspection.image'
    _description = 'Vehicle Inspection Image'

    line_id = fields.Many2one(
        'vehicle.inspection.line',
        string='Inspection Line',
        ondelete='cascade',
        required=True,
    )

    item_id = fields.Many2one(
        related='line_id.item_id',
        store=True,
        readonly=True,
    )

    name = fields.Char(string='Description')

    image = fields.Image(
        string='Image',
        max_width=1920,
        max_height=1920,
        attachment=True,
    )


# class VehicleInspectionImage(models.Model):
#     _name = 'vehicle.inspection.image'
#     _description = 'Vehicle Inspection Image'
#
#     vehicle_inspection_id = fields.Many2one(
#         'vehicle.inspection',
#         string='Vehicle Inspection',
#         ondelete='cascade',
#         required=True,
#     )
#
#     name = fields.Char(string='Description')
#     image = fields.Image(
#         string='Image',
#         max_width=1920,
#         max_height=1920,
#         attachment=True,
#     )


