from odoo import models, fields
from odoo.exceptions import ValidationError


class VehicleNotRunningWizard(models.TransientModel):
    _name = "vehicle.not.running.wizard"
    _description = "Vehicle Not Running Wizard"

    inspection_id = fields.Many2one(
        "vehicle.inspection",
        required=True
    )

    fleet_operations_id = fields.Many2one(
        "hr.employee",
        string="Reporting Manager",
        required=True,
        domain=[('job_id.name', '=', 'Fleet Operations')]
    )

    operator_email = fields.Char(
        related="fleet_operations_id.work_email",
        readonly=True
    )

    comment = fields.Text(
        string="Not Running Comment",
        required=True
    )

    def action_send_not_running_email(self):
        self.ensure_one()

        if not self.operator_email:
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