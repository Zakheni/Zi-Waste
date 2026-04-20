from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class FinishWorksheetWizard(models.TransientModel):
    _name = 'finish.worksheet.wizard'
    _description = 'Finish Worksheet Wizard'

    user_id = fields.Many2one('waste.service.request', string="Target Record", required=True)
    employee_id = fields.Many2one(
        'hr.employee',
        string="Mailto",
        required=True,
        domain=lambda self: [
            ('user_id.groups_id', 'in', self.env.ref('waste_management_zakheni.group_wmz_manager').ids)
        ]
    )

    manager_email = fields.Char(
        related="employee_id.work_email",
        store=True  # ✅ IMPORTANT FIX
    )

    def action_finish_worksheet(self):
        self.ensure_one()

        if not self.user_id:
            _logger.warning("No user_id found on wizard")
            return {'type': 'ir.actions.act_window_close'}

        template = self.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_worksheet_completion',
            raise_if_not_found=False,
        )

        _logger.info("Finish Worksheet USER → %s", self.user_id.id)
        _logger.info("Finish Worksheet → %s", self.manager_email)
        _logger.info("Finish Worksheet  TEMPLATE → %s", template)

        if template and self.manager_email:
            template.sudo().send_mail(
                self.user_id.id,
                force_send=True,
                raise_exception=True,
                email_values={
                    'email_to': self.manager_email
                }
            )
        else:
            _logger.warning(
                "Finish Worksheet email NOT sent. Template: %s, Email: %s",
                template,
                self.manager_email
            )

        return {'type': 'ir.actions.act_window_close'}