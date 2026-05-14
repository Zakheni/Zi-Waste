from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class AuthorizeWizard(models.TransientModel):
    _name = 'authorize.wizard'
    _description = 'Authorize Wizard'

    user_id = fields.Many2one('waste.service.request', string="Target Record", required=True)
    finance_employee_id = fields.Many2one(
        'hr.employee',
        string="Mailto",
        required=True,
        domain=lambda self: [
            ('user_id.groups_id', 'in', self.env.ref('waste_management_zakheni.group_wmz_finance').ids)
        ]
    )

    finance_email = fields.Char(
        related="finance_employee_id.work_email",
        store=True  # ✅ IMPORTANT FIX
    )


    # def action_authorise(self):
    #     self.ensure_one()
    #
    #     if not self.user_id:
    #         _logger.warning("No user_id found on wizard")
    #         return {'type': 'ir.actions.act_window_close'}
    #
    #     template = self.env.ref(
    #         'waste_management_zakheni.mail_tmpl_service_request_authorize',
    #         raise_if_not_found=False,
    #     )
    #
    #     _logger.info("Authorize USER → %s", self.user_id.id)
    #     _logger.info("Authorize EMAIL → %s", self.finance_email)
    #     _logger.info("Authorize TEMPLATE → %s", template)
    #
    #     if template and self.finance_email:
    #         template.sudo().send_mail(
    #             self.user_id.id,
    #             force_send=True,
    #             raise_exception=True,
    #             email_values={
    #                 'email_to': self.finance_email
    #             }
    #         )
    #     else:
    #         _logger.warning(
    #             "Authorize email NOT sent. Template: %s, Email: %s",
    #             template,
    #             self.finance_email
    #         )
    #
    #     return {'type': 'ir.actions.act_window_close'}

    def action_authorise(self):
        self.ensure_one()

        rec = self.user_id.sudo()  # ✅ CORRECT MODEL

        if not rec:
            return {'type': 'ir.actions.act_window_close'}

        # ===============================
        # ✅ YOUR FULL LOGIC HERE
        # ===============================

        # EXAMPLE: update state ONLY NOW
        rec.state = 'done'

        # ===============================
        # ✅ SEND EMAIL
        # ===============================
        template = self.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_authorize',
            raise_if_not_found=False,
        )

        if template and self.finance_email:
            template.sudo().send_mail(
                rec.id,
                force_send=True,
                raise_exception=True,
                email_values={
                    'email_to': self.finance_email
                }
            )

        return {'type': 'ir.actions.act_window_close'}