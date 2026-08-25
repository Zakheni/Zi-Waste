"""Transient wizard to confirm worksheet completion and notify managers.

Workflow step: invoked when a driver or back-office user finishes a waste
worksheet. On confirmation, the worksheet is marked *done*, the linked
service request may advance to *service_delivered*, and a completion email
is sent to the selected WMZ manager.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class FinishWorksheetWizard(models.TransientModel):
    """Wizard to finalize a waste worksheet and trigger manager notification.

    Collects the target worksheet and the manager who should receive the
    completion email. The actual state transitions and mail sending happen
    in :meth:`action_finish_worksheet`.
    """
    _name = 'finish.worksheet.wizard'
    _description = 'Finish Worksheet Wizard'

    user_id = fields.Many2one('waste.worksheet', string="Target Record", required=True)
    employee_id = fields.Many2one(
        'hr.employee',
        string="Mailto",
        required=True,
        domain=lambda self: self.env['hr.employee']._notification_recipient_domain(
            'waste_management_zakheni.group_wmz_user_manager'
        ),
    )

    manager_email = fields.Char(
        related="employee_id.work_email",
        store=True  # ✅ IMPORTANT FIX
    )

    # def action_finish_worksheet(self):
    #     self.ensure_one()
    #
    #     if not self.user_id:
    #         _logger.warning("No user_id found on wizard")
    #         return {'type': 'ir.actions.act_window_close'}
    #
    #     template = self.env.ref(
    #         'waste_management_zakheni.mail_tmpl_service_request_worksheet_completion',
    #         raise_if_not_found=False,
    #     )
    #
    #     _logger.info("Finish Worksheet USER → %s", self.user_id.id)
    #     _logger.info("Finish Worksheet → %s", self.manager_email)
    #     _logger.info("Finish Worksheet  TEMPLATE → %s", template)
    #
    #     if template and self.manager_email:
    #         template.sudo().send_mail(
    #             self.user_id.id,
    #             force_send=True,
    #             raise_exception=True,
    #             email_values={
    #                 'email_to': self.manager_email
    #             }
    #         )
    #     else:
    #         _logger.warning(
    #             "Finish Worksheet email NOT sent. Template: %s, Email: %s",
    #             template,
    #             self.manager_email
    #         )
    #
    #     return {'type': 'ir.actions.act_window_close'}

    def action_finish_worksheet(self):
        """Confirm worksheet completion and notify the selected manager.

        Workflow step: terminal action for the finish-worksheet dialog.

        Side effects:
            - Sets the linked worksheet state to ``done``.
            - If the service request is in a dispatch-related state, sets it
              to ``service_delivered`` (with ``skip_auto_state`` context).
            - Sends ``mail_tmpl_service_request_worksheet_completion`` to
              :attr:`manager_email` when a template and email are available.

        :return: Window-close action for the transient wizard.
        :rtype: dict
        """
        self.ensure_one()

        ws = self.user_id

        if not ws:
            return {'type': 'ir.actions.act_window_close'}

        if self.employee_id:
            ws.write({'employee_id': self.employee_id.id})

        # ✅ UPDATE STATES ONLY AFTER CONFIRM
        ws.state = 'done'

        if ws.service_request_id and ws.service_request_id.state in (
                'scheduled', 'generated', 'dispatched'
        ):
            ws.service_request_id.with_context(skip_auto_state=True).write({
                'state': 'service_delivered'
            })

        # ✅ SEND EMAIL
        template = self.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_worksheet_completion',
            raise_if_not_found=False,
        )

        recipient_email = self.env['hr.employee'].get_notification_email(
            self.employee_id
        )
        if not recipient_email:
            raise UserError(_(
                "The selected User Manager has no email address. "
                "Open Employees, open their record, and set Work Email."
            ))

        if not template:
            raise UserError(_("Worksheet completion email template is missing. Contact your administrator."))

        template.sudo().send_mail(
            ws.id,
            force_send=True,
            raise_exception=True,
            email_values={
                'email_to': recipient_email,
            },
        )

        if self.employee_id.user_id:
            ws.message_subscribe(partner_ids=[self.employee_id.user_id.partner_id.id])

        return {'type': 'ir.actions.act_window_close'}