"""Transient wizard to reject a waste service request with a reason.

Workflow step: allows an authorized user to cancel a service request,
record the rejection reason, and notify an admin clerk by email.
"""
from urllib import request

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class RejectServiceRequestWizard(models.TransientModel):
    """Wizard to reject a service request and notify admin clerks.

    Captures the rejection reason, the target service request, and the
    admin clerk who should receive the rejection notification email.
    """
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
        required=True,
        domain=lambda self: self.env['hr.employee']._notification_recipient_domain(
            'waste_management_zakheni.group_wmz_admin_clerk'
        ),
    )

    admin_clerck_email = fields.Char(
        related="employee_email_id.work_email",
        store=True
    )

    def action_submit_reject_reason(self):
        """Persist rejection details and email the selected admin clerk.

        Workflow step: submit action on the reject-service-request dialog.

        Side effects:
            - Writes ``reject_reason``, sets state to ``cancelled``, and sets
              ``is_rejected`` on the linked service request.
            - Sends ``mail_tmpl_service_request_rejection`` to
              :attr:`admin_clerck_email` when available.

        :return: Window-close action for the transient wizard.
        :rtype: dict
        """
        self.ensure_one()

        if not self.user_id:
            return {'type': 'ir.actions.act_window_close'}

        req = self.user_id.sudo()

        req.write({
            'reject_reason': self.reject_reason,
            'state': 'cancelled',
            'is_rejected': True,
            'employee_email_id': self.employee_email_id.id,
        })

        recipient_email = self.env['hr.employee'].get_notification_email(
            self.employee_email_id
        )
        if not recipient_email:
            raise UserError(_(
                "The selected Admin Clerk has no email address. "
                "Open Employees, open their record, and set Work Email."
            ))

        template = self.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_rejection',
            raise_if_not_found=False,
        )

        _logger.info("Reject email → %s", recipient_email)

        if not template:
            raise UserError(_("Rejection email template is missing. Contact your administrator."))

        template.sudo().send_mail(
            req.id,
            force_send=True,
            raise_exception=True,
            email_values={
                'email_to': recipient_email,
            },
        )

        if self.employee_email_id.user_id:
            req.message_subscribe(partner_ids=[self.employee_email_id.user_id.partner_id.id])

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


