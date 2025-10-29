from odoo import models, fields, api


class DriverSignatureWizard(models.TransientModel):
    _name = 'driver.signature'
    _description = 'Driver Signature Input Wizard'

    create_uid = fields.Many2one('res.users', string="Created by",store=True)
    created_on = fields.Datetime(string="Created On", default=fields.Datetime.now,store=True)
    driver_signature = fields.Binary(string='Signature', required=True,store=True)
    user_id = fields.Many2one('waste.service.request', string="Target Record",store=True)

    def action_enter_signature(self):
        self.ensure_one()
        # self.status = 'send'
        if self.user_id:
            self.user_id.write({
                'driver_signature': self.driver_signature,
            })
        return {'type': 'ir.actions.act_window_close'}


# STORED MODULE
class DriverSignature(models.Model):
    _name = 'driver.signature'
    _description = 'Driver Signature Input'

    create_uid = fields.Many2one('res.users', string="Created by", store=True)
    created_on = fields.Datetime(string="Created On", default=fields.Datetime.now, store=True)
    driver_signature = fields.Binary(string='Signature', required=True, store=True)
    user_id = fields.Many2one('waste.service.request', string="Target Record", store=True)

    def action_enter_signature(self):
        self.ensure_one()
        # self.status = 'send'
        if self.user_id:
            self.user_id.write({
                'driver_signature': self.driver_signature,
            })
        return {'type': 'ir.actions.act_window_close'}

