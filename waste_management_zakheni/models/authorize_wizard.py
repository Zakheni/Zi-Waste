from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class AuthorizeWizard(models.TransientModel):
    _name = 'authorize.wizard'
    _description = 'Authorize Wizard'

    user_id = fields.Many2one('waste.service.request', string="Target Record", required=True)
    finance_employee_id = fields.Many2one('hr.employee', string="Mailto", required=True)

    finance_email = fields.Char(
        related="finance_employee_id.work_email",
        store=True  # ✅ IMPORTANT FIX
    )

    # def action_authorise(self):
    #     self.ensure_one()
    #
    #     if not self.user_id:
    #         _logger.error("No service request linked to wizard")
    #         return {'type': 'ir.actions.act_window_close'}
    #
    #     if not self.finance_email:
    #         _logger.error("No finance email selected")
    #         return {'type': 'ir.actions.act_window_close'}
    #
    #     template = self.env.ref(
    #         'waste_management_zakheni.mail_tmpl_service_request_authorize',
    #         raise_if_not_found=False,
    #     )
    #
    #     _logger.info("Authorize email → %s", self.finance_email)
    #
    #     if template:
    #         template.sudo().send_mail(
    #             self.user_id.id,
    #             force_send=True,
    #             raise_exception=True,
    #             email_values={
    #                 'email_to': self.finance_email,
    #                 'email_cc': False,
    #                 'email_bcc': False,
    #             }
    #         )
    #     else:
    #         _logger.error("Email template NOT found!")
    #
    #     return {'type': 'ir.actions.act_window_close'}

    def action_authorise(self):
        self.ensure_one()

        if not self.user_id:
            _logger.warning("No user_id found on wizard")
            return {'type': 'ir.actions.act_window_close'}

        template = self.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_authorize',
            raise_if_not_found=False,
        )

        _logger.info("Authorize USER → %s", self.user_id.id)
        _logger.info("Authorize EMAIL → %s", self.finance_email)
        _logger.info("Authorize TEMPLATE → %s", template)

        if template and self.finance_email:
            template.sudo().send_mail(
                self.user_id.id,
                force_send=True,
                raise_exception=True,
                email_values={
                    'email_to': self.finance_email
                }
            )
        else:
            _logger.warning(
                "Authorize email NOT sent. Template: %s, Email: %s",
                template,
                self.finance_email
            )

        return {'type': 'ir.actions.act_window_close'}