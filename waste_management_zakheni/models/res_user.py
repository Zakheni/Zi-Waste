from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
import secrets

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'


class ResUsers(models.Model):
    _inherit = 'res.users'

    login = fields.Char(tracking=True)
    name = fields.Char(tracking=True)
    active = fields.Boolean(tracking=True)
    company_id = fields.Many2one('res.company', tracking=True)



    def write(self, vals):
        old_data = {}
        old_groups = {}
        old_companies = {}

        # Store old values before write
        for user in self:
            old_data[user.id] = {
                field: user[field]
                for field in ['login', 'name', 'active', 'company_id']
                if field in vals
            }

            old_groups[user.id] = set(user.groups_id.ids)
            old_companies[user.id] = set(user.company_ids.ids)

        # Perform actual write once
        res = super().write(vals)

        # Track changes after write
        for user in self:
            changes = []

            # --------------------------------
            # Field changes (normal fields)
            # --------------------------------
            for field, old in old_data.get(user.id, {}).items():
                new = user[field]

                if isinstance(old, models.BaseModel):
                    old = old.display_name
                    new = new.display_name if new else False

                if old != new:
                    label = self._fields[field].string
                    changes.append(
                        f"<li><b>{label}</b>: {old} → {new}</li>"
                    )

            # --------------------------------
            # Allowed Companies (Many2many)
            # --------------------------------
            new_companies = set(user.company_ids.ids)
            added_companies = new_companies - old_companies[user.id]
            removed_companies = old_companies[user.id] - new_companies

            if added_companies:
                for company in self.env['res.company'].browse(list(added_companies)):
                    changes.append(
                        f"<li>➕ <b>Allowed Company added</b>: {company.display_name}</li>"
                    )

            if removed_companies:
                for company in self.env['res.company'].browse(list(removed_companies)):
                    changes.append(
                        f"<li>➖ <b>Allowed Company removed</b>: {company.display_name}</li>"
                    )

            # --------------------------------
            # Group changes
            # --------------------------------
            new_groups = set(user.groups_id.ids)
            added_groups = new_groups - old_groups[user.id]
            removed_groups = old_groups[user.id] - new_groups

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

            # --------------------------------
            # Create audit message
            # --------------------------------
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

    # @api.model_create_multi
    # def create(self, vals_list):
    #     creator = self.env.user
    #
    #     if creator.has_group("waste_management_zakheni.group_company_admin"):
    #         for vals in vals_list:
    #             vals["company_id"] = creator.company_id.id
    #             vals["company_ids"] = [(6, 0, [creator.company_id.id])]
    #
    #
    #     return super().create(vals_list)
    #
    # @api.constrains("company_id", "company_ids")
    # def _check_company_assignment_governance(self):
    #     current_user = self.env.user
    #
    #     for user in self:
    #         # Company Admins: cannot touch company fields
    #         if current_user.has_group("waste_management_zakheni.group_company_admin"):
    #             if user.company_id != current_user.company_id:
    #                 raise ValidationError(
    #                     "Company Admins cannot assign users to another company."
    #                 )
    #
    #             if len(user.company_ids) != 1 or user.company_ids[0] != current_user.company_id:
    #                 raise ValidationError(
    #                     "Company Admins cannot assign multiple companies."
    #                 )
    #
    #         # # Non-Central Admins: cannot create shared users
    #         # if len(user.company_ids) > 1:
    #         #     if not current_user.has_group("waste_management_zakheni.group_central_admin"):
    #         #         raise ValidationError(
    #         #             "Only Central Admins can assign users to multiple companies."
    #         #         )
    #
    #         if len(user.company_ids) > 1:
    #             if not (
    #                     current_user.has_group("waste_management_zakheni.group_central_admin")
    #                     or current_user.has_group("base.group_system")
    #             ):
    #                 raise ValidationError(
    #                     "Only Central Admins or System Administrators can assign users to multiple companies."
    #                 )
    #

