"""Authorisation wizard — final manager approval after service delivery."""

from odoo import models, fields


class AuthorizeWizard(models.TransientModel):
    """Collect finance recipient and confirm manifest authorisation."""

    _name = 'authorize.wizard'
    _description = 'Authorize Wizard'

    user_id = fields.Many2one('waste.service.request', string="Target Record", required=True)
    finance_employee_id = fields.Many2one(
        'hr.employee',
        string="Mailto",
        required=True,
        domain=lambda self: [
            ('user_id.groups_id', 'in', self.env.ref('waste_management_zakheni.group_wmz_finance').ids)
        ],
    )
    finance_email = fields.Char(related="finance_employee_id.work_email", store=True)

    def action_authorise(self):
        """
        Confirm authorisation on the linked manifest.

        Delegates to waste.service.request.action_authorise so container
        side-effects always run through the same code path as the UI button.

        Returns:
            dict: Window close action for the wizard dialog.
        """
        self.ensure_one()
        rec = self.user_id.sudo()
        if not rec:
            return {'type': 'ir.actions.act_window_close'}

        rec.action_authorise(finance_email=self.finance_email)
        return {'type': 'ir.actions.act_window_close'}
