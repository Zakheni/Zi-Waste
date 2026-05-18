from odoo import models, fields
from odoo.exceptions import ValidationError


class VehicleFaultWizard(models.TransientModel):
    _name = "vehicle.fault.wizard"
    _description = "Vehicle Fault Wizard"

    inspection_id = fields.Many2one(
        "vehicle.inspection",
        required=True
    )

    reporting_manager_id = fields.Many2one(
        "hr.employee",
        string="Reporting Manager",
        required=True,
        domain=[('job_id.name', '=', 'Reporting Manager')]
    )

    manager_email = fields.Char(
        related="reporting_manager_id.work_email",
        readonly=True
    )

    comment = fields.Text(
        string="Fault Comment",
        required=True
    )

    def action_send_fault_email(self):

        self.ensure_one()

        if not self.manager_email:

            raise ValidationError(
                "Selected manager does not have email address."
            )

        mail_values = {

            'subject': 'Vehicle Fault',

            'body_html': f'''
                <p>
                    Vehicle fault detected.
                </p>

                <p>
                    <strong>Vehicle:</strong>
                    {self.inspection_id.vehicle_id.display_name}
                </p>

                <p>
                    <strong>Inspection:</strong>
                    {self.inspection_id.name}
                </p>

                <p>
                    <strong>Comment:</strong>
                    {self.comment}
                </p>
            ''',

            'email_to': self.manager_email,
        }

        mail = self.env[
            'mail.mail'
        ].create(mail_values)

        mail.send()

        self.inspection_id.state = 'faulty'

        # self.inspection_id.vehicle_id.is_vehicle_available = False

        self.inspection_id.message_post(
            body=f"""
                Fault email sent to:
                {self.reporting_manager_id.name}

                <br/><br/>

                Comment:
                {self.comment}
            """
        )

        return {
            'type': 'ir.actions.act_window_close'
        }

    def action_send_fault_email(self):
        self.ensure_one()

        if not self.manager_email:
            raise ValidationError(
                "Selected Reporting Manger does not have email address."
            )

        template = self.env.ref(
            'vehicle_inspection.mail_template_vehicle_fault'
        )

        template.send_mail(
            self.id,
            force_send=True,
            raise_exception=True,
        )

        self.inspection_id.state = 'faulty'

        # Render template body for chatter/audit trail
        body = template._render_field(
            'body_html',
            [self.id]
        )[self.id]

        self.inspection_id.message_post(
            body=body,
            subject="Vehicle Faulty Email Sent",
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )

        return {
            'type': 'ir.actions.act_window_close'
        }