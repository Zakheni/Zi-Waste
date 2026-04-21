from urllib import request

from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)


class RejectServiceRequestWizard(models.TransientModel):
    _name = 'reject.service.request.wizard'
    _description = 'Reject Service Request Wizard'

    reject_reason = fields.Text(string="Enter Reject Reason", tracking=True,required=True, store=True)
    user_id = fields.Many2one('waste.service.request', string="Target Record", store=True)
    work_sheet_id = fields.Many2one(
        'waste.worksheet',
        string='Worksheet',
        help='Related worksheet that should be updated when request is rejected.',
    )
    state = fields.Selection([
        ('draft', 'draft'),
        ('generated', 'Generated'),
        ('cancelled', 'Rejected'),
        ('done', 'Authorised'),
        ('none', 'None')
    ], default='draft', tracking=True, store=True)

    employee_email_id = fields.Many2one(
        'hr.employee',
        string="Mailto",
        domain=lambda self: [
            ('user_id.groups_id', 'in', self.env.ref('waste_management_zakheni.group_wmz_admin_clerk').ids)
        ]

    )

    admin_clerck_email = fields.Char(
        related="employee_email_id.work_email",
        store=True
    )

    def action_submit_reject_reason(self):
        self.ensure_one()

        if not self.user_id:
            return {'type': 'ir.actions.act_window_close'}

        req = self.user_id.sudo()

        req.write({
            'reject_reason': self.reject_reason,
            'state': 'cancelled',
            'is_rejected': True,
        })

        template = self.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_rejection',
            raise_if_not_found=False,
        )

        _logger.info("Reject email → %s", self.admin_clerck_email)

        if template and self.admin_clerck_email:
            template.sudo().send_mail(
                req.id,
                force_send=True,
                raise_exception=True,
                email_values={
                    'email_to': self.admin_clerck_email
                }
            )
        else:
            _logger.warning("Email NOT sent. Template: %s, Email: %s", template, self.admin_clerck_email)

        return {'type': 'ir.actions.act_window_close'}

    # def action_submit_reject_reason(self):
    #     self.ensure_one()
    #
    #     if not self.user_id:
    #         return {'type': 'ir.actions.act_window_close'}
    #
    #     req = self.user_id.sudo()  # <-- your field is user_id
    #
    #     req.write({
    #         'reject_reason': self.reject_reason,
    #         'state': 'cancelled',
    #         'is_rejected': True,
    #     })
    #
    #     # template = self.env.ref(
    #     #     'waste_management_zakheni.mail_tmpl_service_request_rejection',
    #     #     raise_if_not_found=False,
    #     # )
    #     # if template:
    #     #     template.sudo().send_mail(req.id, force_send=True, raise_exception=False)
    #
    #     template = self.env.ref(
    #         'waste_management_zakheni.mail_tmpl_service_request_rejection',
    #         raise_if_not_found=False,
    #     )
    #
    #     if template and req.admin_clerck_email:
    #         template.sudo().send_mail(
    #             req.id,
    #             force_send=True,
    #             raise_exception=True,  # 🔥 IMPORTANT (so you see errors)
    #             email_values={
    #                 'email_to': req.admin_clerck_email
    #             }
    #         )
    #
    #     if template and self.admin_clerck_email:
    #         template.sudo().send_mail(
    #             req.id,
    #             force_send=True,
    #             raise_exception=True,
    #             email_values={
    #                 'email_to': self.admin_clerck_email
    #             }
    #         )
    #
    #
    #     return {'type': 'ir.actions.act_window_close'}


