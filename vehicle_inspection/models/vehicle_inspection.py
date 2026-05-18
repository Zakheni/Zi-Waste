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

    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        required=True,
        tracking=True,
        domain=[('is_vehicle_available', '=', True)]
    )
    partner_id = fields.Many2one("res.partner")
    inspection_date = fields.Date(default=fields.Date.today, required=True)
    inspector_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    # driver_id = fields.Many2one("hr.employee", string="driver")

    driver_id = fields.Many2one(
        "res.partner",
        string="Driver",
        related="vehicle_id.driver_id",
        store=True,
        readonly=True
    )

    vehicle_description = fields.Text(string="Vehicle Description")
    comment = fields.Text(string="Comment")
    km_open = fields.Float(string="KM Opening")
    km_close = fields.Float(string="KM Closing")
    line_ids = fields.One2many("vehicle.inspection.line", "inspection_id")
    signature = fields.Binary(string="Inspector Signature")
    next_inspection_date = fields.Date()

    has_issue = fields.Boolean(compute="_compute_has_issue", store=True)

    state = fields.Selection([
        ("draft", "Draft"),
        ("faulty", "Faulty"),
        ("not_running", "Not Running"),
        ("resolved", "Resolved"),
        ("done", "Done")
    ], default="draft", tracking=True)

    # vehicle_available = fields.Boolean(
    #     related='vehicle_id.vehicle_available',
    #     store=True,
    #     readonly=True
    # )
    #
    # is_vehicle_available = fields.Boolean(
    #     related='vehicle_id.vehicle_available',
    #     readonly=True
    # )

    @api.onchange('state')
    def _onchange_state_update_vehicle_availability(self):

        for rec in self:

            if not rec.vehicle_id:
                continue

            if rec.state in ['faulty', 'not_running']:

                rec.vehicle_id.is_vehicle_available = False

            else:

                rec.vehicle_id.is_vehicle_available = True

    @api.depends("line_ids.result")
    def _compute_has_issue(self):
        for rec in self:
            rec.has_issue = any(
                line.result == "fault"
                for line in rec.line_ids
            )

    # @api.onchange("inspection_type")
    # def _onchange_inspection_type(self):
    #     self.line_ids = [(5, 0, 0)]
    #     items = self.env["vehicle.inspection.item"].search([])
    #     self.line_ids = [(0, 0, {
    #         "category_id": i.category_id.id,
    #         "item_id": i.id
    #     }) for i in items]

    @api.onchange("inspection_type")
    def _onchange_inspection_type(self):

        if self.line_ids:
            return

        items = self.env[
            "vehicle.inspection.item"
        ].search([
            ("active", "=", True)
        ])

        self.line_ids = [
            (0, 0, {
                "item_id": item.id,
            })
            for item in items
        ]

    def action_draft(self):
        self.state = "draft"

    def action_faulty(self):

        for rec in self:
            rec.state = "faulty"

            rec.message_post(
                body="⚠ Vehicle inspection marked as Faulty."
            )

        return True

    def action_not_running(self):

        for rec in self:
            rec.state = "not_running"

            # rec.vehicle_available = False
            # rec.vehicle_id.is_vehicle_available = False

            rec.message_post(
                body="⛔ Vehicle marked as Not Running."
            )

        return True

    def action_resolved(self):

        for rec in self:
            rec.state = "resolved"

            # rec.vehicle_id.is_vehicle_available = True

            rec.message_post(
                body="✅ Vehicle inspection resolved."
            )

        return True

    def action_done(self):

        for rec in self:
            rec.state = "done"

            rec.message_post(
                body="✅ Inspection completed."
            )

        return True


    def _update_state_from_lines(self):
        """
        Status must ONLY be controlled by buttons.
        Checklist results should never move workflow state.
        """
        return True

    def write(self, vals):

        res = super().write(vals)

        for rec in self:

            if rec.vehicle_id:

                if rec.state in ['faulty', 'not_running']:

                    rec.vehicle_id.is_vehicle_available = False

                else:

                    rec.vehicle_id.is_vehicle_available = True

        return res

    def _send_fault_notification(self):

        template = self.env.ref(
            'vehicle_inspection.email_template_vehicle_fault',
            raise_if_not_found=False
        )

        if template:
            template.send_mail(self.id, force_send=True)

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

    def action_open_fault_wizard(self):

        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Fault Notification',
            'res_model': 'vehicle.fault.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_inspection_id': self.id,
            }
        }

    def action_open_not_running_wizard(self):

        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Not Running Notification',
            'res_model': 'vehicle.not.running.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_inspection_id': self.id,
            }
        }

    def action_open_resolved_wizard(self):

        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Resolved Notification',
            'res_model': 'vehicle.resolved.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_inspection_id': self.id,
            }
        }

    def action_open_resolved_not_running_wizard(self):

        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Resolved Notification',
            'res_model': 'vehicle.resolved.not.running.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_inspection_id': self.id,
            }
        }

    show_fault_button = fields.Boolean(
        compute="_compute_show_fault_button"
    )

    show_resolved_button = fields.Boolean(
        compute="_compute_show_resolved_button"
    )

    show_notify_button = fields.Boolean(
        compute="_compute_show_notify_button"
    )

    @api.depends('line_ids.result')
    def _compute_show_fault_button(self):

        for rec in self:
            rec.show_fault_button = (
                    'fault' in rec.line_ids.mapped('result')
            )

    @api.depends('line_ids.result')
    def _compute_show_notify_button(self):

        for rec in self:
            rec.show_notify_button = (
                    'fault' in rec.line_ids.mapped('result')
            )

    @api.depends('line_ids.result')
    def _compute_show_resolved_button(self):

        for rec in self:
            results = rec.line_ids.mapped('result')

            rec.show_resolved_button = (
                    results
                    and all(r == 'clear' for r in results)
            )


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

    name = fields.Char(string='Description', required=True,)

    image = fields.Image(
        string='Image',
        max_width=1920,
        max_height=1920,
        attachment=True,
    )





