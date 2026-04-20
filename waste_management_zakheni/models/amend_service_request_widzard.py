from urllib import request

from odoo import models, fields, api

import logging
_logger = logging.getLogger(__name__)


class AmendServiceRequestWizard(models.TransientModel):
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
        ('assigned', 'Assigned to Driver'),
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
        domain=lambda self: [
            ('user_id.groups_id', 'in', self.env.ref('waste_management_zakheni.group_wmz_admin_clerk').ids)
        ]

    )

    manager_email = fields.Char(
        related="employee_manager_id.work_email",
        store=True
    )

    def action_submit_amend_comment(self):
        self.ensure_one()

        if self.user_id:
            self.user_id.write({
                'amend_comment': self.amend_comment,
                'state': 'service_delivered',
            })

        template = self.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_amend',
            raise_if_not_found=False,
        )

        _logger.info("Amend email → %s", self.manager_email)

        if template and self.manager_email:
            template.sudo().send_mail(
                self.user_id.id,
                force_send=True,
                raise_exception=True,  # 🔥 so you SEE errors
                email_values={
                    'email_to': self.manager_email
                }
            )
        else:
            _logger.warning(
                "Amend email NOT sent. Template: %s, Email: %s",
                template,
                self.manager_email
            )

        return {'type': 'ir.actions.act_window_close'}





