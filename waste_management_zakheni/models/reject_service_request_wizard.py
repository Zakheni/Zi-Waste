from urllib import request

from odoo import models, fields, api


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

    def action_submit_reject_reason(self):
        self.ensure_one()
        # self.state = 'cancelled'
        if self.user_id:
            self.user_id.write({
                'reject_reason': self.reject_reason,
                'state': 'cancelled',
                'is_rejected': True,
            })

        template = self.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_rejection',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.user_id.id, force_send=True)

        return {'type': 'ir.actions.act_window_close'}


class RejectServiceRequest(models.Model):
    _name = 'reject.service.request.wizard'
    _description = 'Reject Service Request'

    create_uid = fields.Many2one('res.users', string="Created by",store=True)
    reject_reason = fields.Text(string="Enter Reject Reason",tracking=True, required=True,store=True)
    user_id = fields.Many2one('waste.service.request', string="Target Record",store=True)
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
    ], default='draft', tracking=True,store=True)

    def action_submit_reject_reason(self):
        self.ensure_one()

        if self.user_id:
            self.user_id.write({
                'reject_reason': self.reject_reason,
                'state': 'cancelled',
                'is_rejected': True,
            })

        template = self.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_rejection',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.user_id.id, force_send=True)

        return {'type': 'ir.actions.act_window_close'}
