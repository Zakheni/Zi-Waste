"""Core vehicle inspection model and related image records."""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class VehicleInspection(models.Model):
    """Vehicle inspection record with checklist, workflow, and notifications.

    Supports internal fleet and customer/garage inspections. Workflow states
    are controlled exclusively by header buttons, not by checklist results.
    """

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

    # @api.model
    # def create(self, vals):
    #     if vals.get('name', 'New') == 'New':
    #         vals['name'] = self.env['ir.sequence'].next_by_code('vehicle.inspection') or 'New'
    #
    #     return super().create(vals)

    @api.model
    def default_get(self, fields_list):
        """
        Pre-populate inspection lines from active categories and checklist items.

        Returns:
            dict: Default values including line_ids command list.
        """
        res = super().default_get(fields_list)

        lines = []
        categories = self.env['vehicle.inspection.category'].search(
            [('active', '=', True)],
            order='sequence',
        )

        for category in categories:
            lines.append((0, 0, {
                'display_type': 'line_section',
                'name': category.name,
            }))

            items = self.env['vehicle.inspection.item'].search([
                ('category_id', '=', category.id),
                ('active', '=', True),
            ])

            for item in items:
                lines.append((0, 0, {
                    'item_id': item.id,
                }))

        res['line_ids'] = lines
        return res

    @api.model
    def create(self, vals):
        """Assign a sequence reference when creating a new inspection.

        Args:
            vals (dict): Values for the new record.

        Returns:
            recordset: Newly created inspection record(s).
        """
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env[
                               'ir.sequence'
                           ].next_by_code(
                'vehicle.inspection'
            ) or 'New'

        return super().create(vals)
    inspection_type = fields.Selection([
        ("fleet", "Internal Fleet"),
        ("customer", "Customer / Garage")
    ], default="fleet", required=True)

    @api.model
    def _vehicle_id_domain(self):
        """Exclude vehicles tied to open inspections."""
        busy_ids = self.env['vehicle.inspection'].with_context(active_test=False).search([
            ('state', 'in', ['faulty', 'not_running', 'draft']),
        ]).mapped('vehicle_id').ids
        return [('id', 'not in', busy_ids or [0])]

    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        required=True,
        tracking=True,
        domain=_vehicle_id_domain,
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
    active = fields.Boolean(default=True)

    has_issue = fields.Boolean(compute="_compute_has_issue", store=True)

    checklist_total = fields.Integer(compute="_compute_checklist_stats")
    checklist_clear_count = fields.Integer(compute="_compute_checklist_stats", string="Clear")
    checklist_fault_count = fields.Integer(compute="_compute_checklist_stats", string="Faults")
    checklist_pending_count = fields.Integer(compute="_compute_checklist_stats", string="Pending")
    checklist_progress = fields.Float(
        compute="_compute_checklist_stats",
        string="Checklist Progress (%)",
    )

    state = fields.Selection([
        ("draft", "Draft"),
        ("faulty", "Faulty"),
        ("not_running", "Not Running"),
        ("resolved", "Resolved"),
        ("done", "Done")
    ], default="draft", tracking=True)

    @api.onchange('state')
    def _onchange_state_update_vehicle_availability(self):
        """Sync fleet vehicle availability when state changes in the form."""
        for rec in self:

            if not rec.vehicle_id:
                continue

            if rec.state in ['not_running']:

                rec.vehicle_id.is_vehicle_available = False

            else:

                rec.vehicle_id.is_vehicle_available = True

    @api.depends("line_ids.result")
    def _compute_has_issue(self):
        """Set has_issue when any checklist line is marked as fault."""
        for rec in self:
            rec.has_issue = any(
                line.result == "fault"
                for line in rec.line_ids
            )

    @api.depends('line_ids.result', 'line_ids.display_type')
    def _compute_checklist_stats(self):
        for rec in self:
            items = rec.line_ids.filtered(lambda line: line.display_type != 'line_section')
            total = len(items)
            clear = len(items.filtered(lambda line: line.result == 'clear'))
            fault = len(items.filtered(lambda line: line.result == 'fault'))
            answered = clear + fault
            rec.checklist_total = total
            rec.checklist_clear_count = clear
            rec.checklist_fault_count = fault
            rec.checklist_pending_count = total - answered
            rec.checklist_progress = (answered * 100.0 / total) if total else 0.0

    def action_draft(self):
        """Reset the inspection workflow state to draft."""
        self.state = "draft"

    def action_faulty(self):
        """Mark the inspection as faulty and post a chatter message.

        Returns:
            bool: True on success.
        """
        for rec in self:
            rec.state = "faulty"

            rec.message_post(
                body="⚠ Vehicle inspection marked as Faulty."
            )

        return True

    def action_not_running(self):
        """Mark the inspection as not running and post a chatter message.

        Returns:
            bool: True on success.
        """
        for rec in self:
            rec.state = "not_running"

            # rec.vehicle_available = False
            # rec.vehicle_id.is_vehicle_available = False

            rec.message_post(
                body="⛔ Vehicle marked as Not Running."
            )

        return True

    def action_resolved(self):
        """Mark the inspection as resolved and post a chatter message.

        Returns:
            bool: True on success.
        """
        for rec in self:
            rec.state = "resolved"

            # rec.vehicle_id.is_vehicle_available = True

            rec.message_post(
                body="✅ Vehicle inspection resolved."
            )

        return True

    def action_done(self):
        """Complete the inspection after validating required fault photos.

        Marks the vehicle available, archives the record, and posts a message.

        Returns:
            bool: True on success.

        Raises:
            ValidationError: When a fault line requires photos but has none.
        """
        for rec in self:
            rec.state = "done"

            rec.vehicle_id.is_vehicle_available = True

            rec.active = False

            rec.message_post(
                body="✅ Inspection completed."
            )

            for line in self.line_ids:

                if (
                        line.result == 'fault'
                        and line.require_photo
                        and len(line.photo_ids) == 0
                ):
                    raise ValidationError(
                        f"Please upload at least one photo for '{line.item_id.name}'."
                    )

        return True


    def _update_state_from_lines(self):
        """
        Status must ONLY be controlled by buttons.
        Checklist results should never move workflow state.
        """
        return True

    def write(self, vals):
        """Persist changes and sync vehicle availability with inspection state.

        Args:
            vals (dict): Field values to write.

        Returns:
            bool: Result of the parent write call.
        """
        res = super().write(vals)

        for rec in self:

            if rec.vehicle_id:

                if rec.state in ['not_running']:

                    rec.vehicle_id.is_vehicle_available = False

                else:

                    rec.vehicle_id.is_vehicle_available = True

        return res

    def _send_fault_notification(self):
        """Send the fault email template for this inspection."""
        template = self.env.ref(
            'vehicle_inspection.email_template_vehicle_fault',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=True)

    @api.model
    def cron_schedule_inspection_reminders(self):
        """
        Daily cron: create todo activities for inspections due within 7 days.

        Only targets draft or completed inspections with a next_inspection_date set.
        """
        from datetime import timedelta
        today = fields.Date.context_today(self)
        deadline = today + timedelta(days=7)
        records = self.search([
            ('next_inspection_date', '!=', False),
            ('next_inspection_date', '<=', deadline),
            ('state', 'in', ['draft', 'done']),
        ])
        for rec in records:
            rec.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=rec.next_inspection_date,
                summary='Upcoming Vehicle Inspection',
            )

    @api.constrains("inspection_type", "vehicle_id", "partner_id")
    def _check_inspection_target(self):
        """Validate that fleet inspections have a vehicle and customer ones a partner.

        Raises:
            ValidationError: When the required target record is missing.
        """
        for rec in self:
            if rec.inspection_type == "fleet" and not rec.vehicle_id:
                raise ValidationError("Fleet inspections require a vehicle.")
            if rec.inspection_type == "customer" and not rec.partner_id:
                raise ValidationError("Customer inspections require a customer.")

    def action_print_inspection_report(self):
        """Launch the PDF inspection report for this record.

        Returns:
            dict: Report action for the vehicle inspection QWeb template.
        """
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
        """Collect checklist items already present on the inspection lines."""
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
        """Aggregate all photos from inspection lines for the Photos tab."""
        for inspection in self:
            inspection.image_ids = inspection.line_ids.mapped('photo_ids')

    def action_open_fault_wizard(self):
        """Open the fault notification wizard for this inspection.

        Returns:
            dict: Window action for vehicle.fault.wizard.
        """
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
        """Open the not-running notification wizard for this inspection.

        Returns:
            dict: Window action for vehicle.not.running.wizard.
        """
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
        """Open the resolved notification wizard for this inspection.

        Returns:
            dict: Window action for vehicle.resolved.wizard.
        """
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
        """Open the resolved-not-running wizard for this inspection.

        Returns:
            dict: Window action for vehicle.resolved.not.running.wizard.
        """
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
        """Show the Faulty button when any line result is fault."""
        for rec in self:
            rec.show_fault_button = (
                    'fault' in rec.line_ids.mapped('result')
            )

    @api.depends('line_ids.result')
    def _compute_show_notify_button(self):
        """Show notification buttons when any line result is fault."""
        for rec in self:
            rec.show_notify_button = (
                    'fault' in rec.line_ids.mapped('result')
            )

    @api.depends('line_ids.result')
    def _compute_show_resolved_button(self):
        """Show the Resolved button when every line result is clear."""
        for rec in self:
            results = rec.line_ids.mapped('result')

            rec.show_resolved_button = (
                    results
                    and all(r == 'clear' for r in results)
            )


class VehicleInspectionImage(models.Model):
    """Photo attached to an inspection line with a required description."""

    _name = 'vehicle.inspection.image'
    _description = 'Vehicle Inspection Image'

    line_id = fields.Many2one(
        'vehicle.inspection.line',
        string='Inspection Line',
        ondelete='cascade',

    )

    item_id = fields.Many2one(
        related='line_id.item_id',
        store=True,
        readonly=True,
    )

    name = fields.Char(string='Description', )

    image = fields.Image(
        string='Image',
        max_width=1920,
        max_height=1920,
        attachment=True,
    )

    @api.constrains('name', 'image')
    def _check_photo_and_description(self):
        """Require both an image file and a description on every photo.

        Raises:
            ValidationError: When image or description is missing.
        """
        for rec in self:

            if not rec.image:
                raise ValidationError(
                    "Please upload a photo."
                )

            if not rec.name:
                raise ValidationError(
                    "Please enter a photo description."
                )

    def write(self, vals):
        """Block photo edits on completed inspections.

        Args:
            vals (dict): Field values to write.

        Returns:
            bool: Result of the parent write call.

        Raises:
            ValidationError: When the parent inspection is done.
        """
        for rec in self:
            if rec.line_id.inspection_id.state == 'done':
                raise ValidationError(
                    "You cannot modify photos on a completed inspection."
                )

        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Block photo creation on completed inspections.

        Args:
            vals_list (list[dict]): Values for new photo records.

        Returns:
            recordset: Newly created photo record(s).

        Raises:
            ValidationError: When the parent inspection is done.
        """
        for vals in vals_list:

            if vals.get('line_id'):

                line = self.env['vehicle.inspection.line'].browse(
                    vals['line_id']
                )

                if line.inspection_id.state == 'done':
                    raise ValidationError(
                        "You cannot add photos to a completed inspection."
                    )

        return super().create(vals_list)

    def unlink(self):
        """Block photo deletion on completed inspections.

        Returns:
            bool: Result of the parent unlink call.

        Raises:
            ValidationError: When the parent inspection is done.
        """
        for rec in self:

            if rec.line_id.inspection_id.state == 'done':
                raise ValidationError(
                    "You cannot delete photos from a completed inspection."
                )

        return super().unlink()



