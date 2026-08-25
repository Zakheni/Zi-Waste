"""Driver signature capture wizard for waste service requests."""

from odoo import models, fields


class DriverSignatureWizard(models.TransientModel):
    """Transient wizard to capture a driver signature on a manifest."""

    _name = 'driver.signature'
    _description = 'Driver Signature Input Wizard'

    create_uid = fields.Many2one('res.users', string="Created by", store=True)
    created_on = fields.Datetime(string="Created On", default=fields.Datetime.now, store=True)
    driver_signature = fields.Binary(string='Signature', required=True, store=True)
    user_id = fields.Many2one('waste.service.request', string="Target Record", store=True)

    def action_enter_signature(self):
        """
        Save the captured signature onto the linked service request.

        Returns:
            dict: Window close action for the wizard dialog.
        """
        self.ensure_one()
        if self.user_id:
            self.user_id.write({
                'driver_signature': self.driver_signature,
            })
        return {'type': 'ir.actions.act_window_close'}
