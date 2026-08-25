"""Transient wizard for sending not-running notification emails."""

from odoo import models, fields
from odoo.exceptions import ValidationError


class VehicleNotRunningWizard(models.TransientModel):
    """Wizard to notify the fleet manager when a vehicle is not running.

    Collects the manager, email address, and comment, then sends the
    configured mail template and updates the inspection state.
    """

    _name = "vehicle.not.running.wizard"
    _description = "Vehicle Not Running Wizard"

    inspection_id = fields.Many2one(
        "vehicle.inspection",
        required=True
    )

    reporting_manager_id = fields.Many2one(
        "hr.employee",
        string="Fleet Manager",
        required=True,
        domain=[('job_id.name', '=', 'Fleet Manager')]
    )

    manager_email = fields.Char(
        related="reporting_manager_id.work_email",
        readonly=True
    )

    comment = fields.Text(
        string="Not Running Comment",
        required=True
    )

    def action_send_not_running_email(self):
        """Send the not-running mail template and update inspection state.

        Returns:
            dict: Window close action after the email is sent.

        Raises:
            ValidationError: If the selected manager has no email address.
        """
        self.ensure_one()

        if not self.manager_email:
            raise ValidationError(
                "Selected Operator does not have email address."
            )

        template = self.env.ref(
            'vehicle_inspection.mail_template_vehicle_not_running'
        )

        template.send_mail(
            self.id,
            force_send=True,
            raise_exception=True,
        )

        self.inspection_id.state = 'not_running'

        # Render template body for chatter/audit trail
        body = template._render_field(
            'body_html',
            [self.id]
        )[self.id]

        self.inspection_id.message_post(
            body=body,
            subject="Vehicle Not Running Email Sent",
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )

        return {
            'type': 'ir.actions.act_window_close'
        }
