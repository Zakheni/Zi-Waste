"""Password management wizard for company-scoped user administrators."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class WmzUserPasswordWizard(models.TransientModel):
    """Set a new password or email a reset link for a provisioned backend user."""

    _name = 'wmz.user.password.wizard'
    _description = 'WMZ User Password Wizard'

    provision_id = fields.Many2one('wmz.service.request.user', readonly=True)
    user_id = fields.Many2one('res.users', required=True, readonly=True)
    login = fields.Char(string='Login', readonly=True)
    new_password = fields.Char(string='New Password')
    confirm_password = fields.Char(string='Confirm Password')
    send_reset_email = fields.Boolean(
        string='Email reset link instead',
        default=False,
        help='When checked, sends Odoo password reset email and skips manual password entry.',
    )

    @api.constrains('new_password', 'confirm_password', 'send_reset_email')
    def _check_passwords(self):
        for wizard in self:
            if wizard.send_reset_email:
                continue
            if wizard.new_password and wizard.new_password != wizard.confirm_password:
                raise ValidationError(_('Password and confirmation must match.'))

    def _check_access(self):
        self.ensure_one()
        if self.provision_id:
            self.provision_id._check_manage_target_user()
            return
        creator = self.env.user
        target = self.user_id
        can_multi = self.env['wmz.service.request.user']._can_manage_multiple_companies(creator)
        if not can_multi and target.company_id not in creator.company_ids:
            raise UserError(_('You can only change passwords for users in your own company.'))

    def action_apply(self):
        self.ensure_one()
        self._check_access()
        if self.send_reset_email:
            self.user_id.sudo().action_reset_password()
            if self.provision_id and self.provision_id.partner_id:
                invite_url = self.provision_id._build_reset_link(self.provision_id.partner_id)
                self.provision_id.write({
                    'invite_url': invite_url,
                    'message': _(
                        '<strong>Password reset email sent.</strong><br/>'
                        '<a href="%s" target="_blank">%s</a>'
                    ) % (invite_url, invite_url),
                    'state': 'created',
                })
            return {'type': 'ir.actions.act_window_close'}

        if not self.new_password:
            raise UserError(_('Enter a new password or choose "Email reset link instead".'))
        self.user_id.sudo()._change_password(self.new_password)
        self.new_password = False
        self.confirm_password = False
        if self.provision_id:
            self.provision_id.write({
                'message': _('Password updated successfully by administrator.'),
                'state': 'created',
            })
        return {'type': 'ir.actions.act_window_close'}
