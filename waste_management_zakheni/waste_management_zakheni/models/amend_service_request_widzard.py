"""Transient wizard to amend a delivered service request.

Workflow step: records an amend comment on a service request that has
reached *service_delivered* and notifies a User Manager (Manager position) by email.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class AmendServiceRequestWizard(models.TransientModel):
    """Wizard to submit an amend comment and notify a User Manager."""

    _name = 'amend.service.request.wizard'
    _description = 'Amend Service Request Wizard'

    amend_comment = fields.Text(string="Enter Amend Comment", tracking=True, store=True)
    user_id = fields.Many2one('waste.service.request', string="Target Record", store=True)
    work_sheet_id = fields.Many2one(
        'waste.worksheet',
        string='Worksheet',
        help='Related worksheet that should be updated when request is rejected.',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('generated', 'Generated'),
        ('dispatched', 'Dispatched'),
        ('service_delivered', 'Service Delivered'),
        ('cancelled', 'Rejected'),
        ('done', 'Authorised'),
        ('none', 'None'),
    ], default='draft', tracking=True)

    employee_manager_id = fields.Many2one(
        'hr.employee',
        string="Mailto",
        required=True,
        domain=lambda self: self.env['hr.employee']._notification_recipient_domain(
            'waste_management_zakheni.group_wmz_user_manager',
            job_name='Manager',
        ),
    )

    manager_email = fields.Char(
        related="employee_manager_id.work_email",
        store=True,
    )

    def action_submit_amend_comment(self):
        """Save the amend comment and email the selected User Manager."""
        self.ensure_one()

        if not self.user_id:
            return {'type': 'ir.actions.act_window_close'}

        req = self.user_id.sudo()
        req.write({
            'amend_comment': self.amend_comment,
            'state': 'service_delivered',
            'employee_manager_id': self.employee_manager_id.id,
        })

        recipient_email = self.env['hr.employee'].get_notification_email(
            self.employee_manager_id
        )
        if not recipient_email:
            raise UserError(_(
                "The selected User Manager has no email address. "
                "Open Employees, open their record, and set Work Email."
            ))

        template = self.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_amend',
            raise_if_not_found=False,
        )
        if not template:
            raise UserError(_("Amend email template is missing. Contact your administrator."))

        _logger.info("Amend email → %s", recipient_email)

        template.sudo().send_mail(
            req.id,
            force_send=True,
            raise_exception=True,
            email_values={
                'email_to': recipient_email,
            },
        )

        if self.employee_manager_id.user_id:
            req.message_subscribe(partner_ids=[self.employee_manager_id.user_id.partner_id.id])

        return {'type': 'ir.actions.act_window_close'}
