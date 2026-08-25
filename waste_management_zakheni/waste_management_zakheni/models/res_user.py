"""Extensions to res.users for waste management portal governance and mobile auth."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
import secrets

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'


class ResUsers(models.Model):
    """Track user changes, validate login email, and expose mobile API tokens."""

    _inherit = 'res.users'

    login = fields.Char(tracking=True)
    name = fields.Char(tracking=True)
    active = fields.Boolean(tracking=True)
    company_id = fields.Many2one('res.company', tracking=True)
    api_token = fields.Char(
        string="Mobile API Token",
        copy=False,
        groups='base.group_system,waste_management_zakheni.group_wmz_admin',
    )
    wmz_driver_partner_ids = fields.Many2many(
        'res.partner',
        'res_users_wmz_driver_partner_rel',
        'user_id',
        'partner_id',
        string='WMZ Driver Partners',
        compute='_compute_wmz_driver_partner_ids',
        store=True,
        help='Partner records linked to this user for fleet driver assignments and worksheet record rules.',
    )
    wmz_driver_partner_id = fields.Many2one(
        'res.partner',
        string='WMZ Driver Partner',
        compute='_compute_wmz_driver_partner_id',
        store=True,
        index=True,
        help='Primary partner record matched to fleet driver assignments for record rules and mobile APIs.',
    )

    @api.depends('partner_id', 'employee_ids.work_contact_id', 'login')
    def _compute_wmz_driver_partner_ids(self):
        """Collect every partner that may identify this user as a fleet driver."""
        Partner = self.env['res.partner']
        Vehicle = self.env['fleet.vehicle']
        Employee = self.env['hr.employee']
        for user in self:
            partners = Partner
            if user.partner_id:
                partners |= user.partner_id
            for employee in user.employee_ids:
                if employee.work_contact_id:
                    partners |= employee.work_contact_id
            for employee in Employee.search([('user_id', '=', user.id)]):
                if employee.work_contact_id:
                    partners |= employee.work_contact_id
            login = (user.login or '').strip()
            if login:
                partners |= Partner.search([
                    ('email', '=ilike', login),
                    '|', ('company_id', '=', False), ('company_id', '=', user.company_id.id),
                ])
            if partners:
                partners |= Vehicle.search([
                    ('driver_id', 'in', partners.ids),
                ]).mapped('driver_id')
            user.wmz_driver_partner_ids = partners

    @api.depends('wmz_driver_partner_ids')
    def _compute_wmz_driver_partner_id(self):
        """Resolve the primary res.partner used on manifests, worksheets, and fleet vehicles."""
        for user in self:
            user.wmz_driver_partner_id = user.wmz_driver_partner_ids[:1]

    def _generate_api_token(self):
        """Return a new random bearer token for mobile authentication."""
        return secrets.token_urlsafe(32)

    def ensure_api_token(self):
        """
        Ensure each user has a mobile API token, generating one when missing.

        Returns:
            str: The user's api_token value.
        """
        for user in self:
            if not user.api_token:
                user.sudo().write({'api_token': user._generate_api_token()})
        return self.api_token

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

        if {'company_id', 'company_ids', 'partner_id'} & set(vals):
            self._wmz_sync_partner_company()

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

    def _wmz_can_assign_multiple_companies(self):
        """Return True when the current user may grant multi-company access."""
        user = self.env.user
        return user.has_group('base.group_system') or user.has_group(
            'waste_management_zakheni.group_central_admin'
        ) or user.has_group('waste_management_zakheni.group_wmz_admin')

    def _wmz_enforce_creator_company(self, vals):
        """Force single-company assignment for company-scoped administrators."""
        creator = self.env.user
        if creator._is_public() or creator._is_portal():
            return
        if self._wmz_can_assign_multiple_companies():
            return
        if not (
            creator.has_group('waste_management_zakheni.group_company_admin')
            or creator.has_group('waste_management_zakheni.group_wmz_user_manager')
        ):
            return
        company_id = creator.company_id.id
        vals['company_id'] = company_id
        vals['company_ids'] = [(6, 0, [company_id])]

    def _wmz_sync_partner_company(self):
        """Keep linked partner.company_id aligned with the user's primary company."""
        for user in self:
            if not user.partner_id or not user.company_id:
                continue
            partner = user.partner_id
            if partner.company_id != user.company_id:
                partner.sudo().write({'company_id': user.company_id.id})

    @api.model_create_multi
    def create(self, vals_list):
        """Ensure linked partners have a customer reference before user creation."""
        Partner = self.env['res.partner'].sudo()
        for vals in vals_list:
            self._wmz_enforce_creator_company(vals)
            partner_id = vals.get('partner_id')
            if not partner_id:
                continue
            partner = Partner.browse(partner_id)
            if partner._needs_customer_reference():
                partner.write({
                    'customer_reference': partner._next_customer_reference(),
                })
            if vals.get('company_id') and partner.company_id.id != vals['company_id']:
                partner.write({'company_id': vals['company_id']})
        users = super().create(vals_list)
        users._wmz_sync_partner_company()
        return users

    @api.constrains('company_id', 'company_ids')
    def _check_company_assignment_governance(self):
        """POPIA: restrict cross-company and multi-company user assignment."""
        if self.env.su:
            return
        current_user = self.env.user
        if current_user._is_public() or current_user._is_portal():
            return

        can_multi = self._wmz_can_assign_multiple_companies()

        for user in self:
            if (
                current_user.has_group('waste_management_zakheni.group_company_admin')
                or current_user.has_group('waste_management_zakheni.group_wmz_user_manager')
            ) and not can_multi:
                if user.company_id != current_user.company_id:
                    raise ValidationError(_(
                        "Company Administrators cannot assign users to another company."
                    ))
                if len(user.company_ids) != 1 or user.company_ids[0] != current_user.company_id:
                    raise ValidationError(_(
                        "Company Administrators cannot assign multiple companies."
                    ))

            if len(user.company_ids) > 1 and not can_multi:
                raise ValidationError(_(
                    "Only Central Administrators or Super Admins "
                    "can assign users to multiple companies."
                ))

            if user.company_id and user.company_id not in user.company_ids:
                raise ValidationError(_(
                    "The user's primary company must be included in Allowed Companies."
                ))


