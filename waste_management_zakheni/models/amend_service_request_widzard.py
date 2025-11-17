from urllib import request

from odoo import models, fields, api


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

    def action_submit_amend_comment(self):
        self.ensure_one()

        # self.state = 'cancelled'
        if self.user_id:
            self.user_id.write({
                'amend_comment': self.amend_comment,
                'state': 'service_delivered',
            })

        template = self.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_amend',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.user_id.id, force_send=True)

        return {'type': 'ir.actions.act_window_close'}


class AmendServiceRequest(models.TransientModel):
    _name = 'amend.service.request.wizard'
    _description = 'Amend Service Request'

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

    def action_submit_amend_comment(self):
        self.ensure_one()

        # self.state = 'cancelled'
        if self.user_id:
            self.user_id.write({
                'amend_comment': self.amend_comment,
                'state': 'service_delivered',
            })

        template = self.env.ref(
            'waste_management_zakheni.mail_tmpl_service_request_amend',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.user_id.id, force_send=True)

        return {'type': 'ir.actions.act_window_close'}



