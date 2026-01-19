from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'


class ResUsers(models.Model):
    _inherit = 'res.users'

    login = fields.Char(tracking=True)
    name = fields.Char(tracking=True)
    active = fields.Boolean(tracking=True)
    company_id = fields.Many2one('res.company', tracking=True)

    def write(self, vals):
        for user in self:
            changes = []

            # --------------------------------------------------
            # Track simple field changes (your existing logic)
            # --------------------------------------------------
            for field in ['login', 'name', 'active', 'company_id']:
                if field in vals:
                    old = user[field]
                    new = vals[field]

                    if isinstance(old, models.BaseModel):
                        old = old.display_name
                        new = self.env[old._name].browse(new).display_name if new else False

                    if old != new:
                        changes.append(
                            f"<li><b>{field}</b>: {old} → {new}</li>"
                        )

            # --------------------------------------------------
            # Track GROUP (permission) changes 🔐
            # --------------------------------------------------
            old_groups = set(user.groups_id.ids)

            # Perform the actual write
            res = super(ResUsers, user).write(vals)

            new_groups = set(user.groups_id.ids)

            added_groups = new_groups - old_groups
            removed_groups = old_groups - new_groups

            if added_groups:
                for group in self.env['res.groups'].browse(list(added_groups)):
                    changes.append(
                        f"<li>➕ <b>Group added</b>: {group.display_name}</li>"
                    )

            if removed_groups:
                for group in self.env['res.groups'].browse(list(removed_groups)):
                    changes.append(
                        f"<li>➖ <b>Group removed</b>: {group.display_name}</li>"
                    )

            # --------------------------------------------------
            # Create ONE audit log entry (if anything changed)
            # --------------------------------------------------
            if changes:
                self.env['mail.message'].create({
                    'model': 'res.users',
                    'res_id': user.id,
                    'message_type': 'notification',
                    'body': "<ul>%s</ul>" % "".join(changes),
                    'author_id': self.env.user.partner_id.id,
                })

            return res

    @classmethod
    def _get_signup_fields(cls):
        fields = super()._get_signup_fields()
        if 'wmz_portal_group' not in fields:
            fields.append('wmz_portal_group')
        return fields

    audit_message_ids = fields.Many2many(
        'mail.message',
        compute='_compute_audit_messages',
        string='Audit Trail',
        readonly=True,
    )

    def _compute_audit_messages(self):
        MailMessage = self.env['mail.message']
        for user in self:
            user.audit_message_ids = MailMessage.search([
                ('model', '=', 'res.users'),
                ('res_id', '=', user.id),
                ('message_type', 'in', ['notification', 'comment']),
            ], order='date desc')

    @api.constrains('login')
    def _check_login_email_format(self):
        for user in self:
            if user.login:
                login = user.login.strip()
                if not re.match(EMAIL_REGEX, login):
                    raise ValidationError(_(
                        "Invalid email format.\n"
                        "Example:✅ email@example.com\n"
                        "Not allowed:❌ %s"
                    ) % login)

