"""Transient wizard for sending resolved notification emails."""

from odoo import models, fields
from odoo.exceptions import ValidationError


class VehicleResolvedWizard(models.TransientModel):
    """Wizard to notify the fleet manager when a faulty inspection is resolved.

    Collects the manager, email address, and resolution comment, then
    sends the configured mail template and updates the inspection state.
    """

    _name = "vehicle.resolved.wizard"
    _description = "Vehicle Resolved Wizard"

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
        string="Fault Comment",
        required=True
    )

    def action_send_resolved_email(self):
        """Send the resolved mail template and mark the inspection resolved.

        Returns:
            dict: Window close action after the email is sent.

        Raises:
            ValidationError: If the selected manager has no email address.
        """
        self.ensure_one()

        if not self.manager_email:
            raise ValidationError(
                "Selected Reporting manager does not have email address."
            )

        template = self.env.ref(
            'vehicle_inspection.mail_template_vehicle_resolved'
        )

        template.send_mail(
            self.id,
            force_send=True,
            raise_exception=True,
        )

        self.inspection_id.state = 'resolved'

        # Render template body for chatter/audit trail
        body = template._render_field(
            'body_html',
            [self.id]
        )[self.id]

        self.inspection_id.message_post(
            body=body,
            subject="Vehicle Resolved Email Sent",
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )

        return {
            'type': 'ir.actions.act_window_close'
        }
