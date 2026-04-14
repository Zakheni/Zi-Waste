from odoo import models, fields
from odoo.exceptions import UserError


class ServiceRequestUser(models.Model):
    _name = 'wmz.service.request.user'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    service_request_id = fields.Many2one('waste.service.request')

    name = fields.Char(required=True, tracking=True)
    email = fields.Char(required=True, tracking=True)
    phone = fields.Char(tracking=True)
    last_login = fields.Datetime(
        string="Last Login",
        related="user_id.login_date",
        readonly=True,
        store=False
    )
    is_online = fields.Boolean(compute="_compute_online")

    lang = fields.Selection(
        related="user_id.lang",
        string="Language",
        readonly=True
    )

    # 🏢 Company
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True
    )

    # 🏢 (Optional) Multi-company access
    company_ids = fields.Many2many(
        'res.company',
        related="user_id.company_ids",
        string="Allowed Companies",
        readonly=True
    )

    status = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('not_confirmed', 'Not Confirmed'),
    ], compute='_compute_status', store=False)

    def _compute_status(self):
        for rec in self:
            if rec.user_id and rec.user_id.login_date:
                rec.status = 'confirmed'
            else:
                rec.status = 'not_confirmed'

    def _compute_online(self):
        for rec in self:
            if rec.last_login:
                delta = fields.Datetime.now() - rec.last_login
                rec.is_online = delta.total_seconds() < 300

    role_ids = fields.Many2many(
        'res.groups',
        string="Roles",
        domain=[
            ('category_id.name', 'in', [
                'Waste Management',
                'Pastel Connector',
                'Vehicle Inspection'
            ])
        ],
        required=True,
        tracking=True
    )

    # role_ids = fields.Many2many(
    #     'res.groups',
    #     string="Roles"
    # )

    user_id = fields.Many2one('res.users', readonly=True)
    partner_id = fields.Many2one('res.partner', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('created', 'Created'),
        ('error', 'Error'),
    ], default='draft', tracking=True)

    # message = fields.Text()
    # message = fields.Text(readonly=True)
    message = fields.Html(string="Message", readonly=True)
    invite_url = fields.Char(string="Invitation Link", readonly=True)

    # def action_create_user(self):
    #     for rec in self:
    #         try:
    #             # 🔴 CHECK duplicate
    #
    #             existing = self.env['res.users'].sudo().search([
    #                 ('login', '=', rec.email)
    #             ], limit=1)
    #
    #             if existing:
    #                 rec.write({
    #                     'user_id': existing.id,
    #                     'partner_id': existing.partner_id.id,
    #                     'state': 'error',
    #                     'message': 'User already exists with this email'
    #                 })
    #                 continue
    #
    #             # ✅ CREATE PARTNER
    #             partner = self.env['res.partner'].sudo().create({
    #                 'name': rec.name,
    #                 'email': rec.email,
    #                 'phone': rec.phone,
    #             })
    #
    #             # ✅ CREATE USER (ONLY ONCE)
    #             user = self.env['res.users'].sudo().create({
    #                 'name': rec.name,
    #                 'login': rec.email,
    #                 'email': rec.email,
    #                 'partner_id': partner.id,
    #                 'active': True,
    #             })
    #
    #             # ✅ PREPARE GROUPS
    #             groups = []
    #
    #             # Add selected roles
    #             if rec.role_ids:
    #                 groups.extend(rec.role_ids.ids)
    #
    #             # Always include internal user
    #             base_group = self.env.ref('base.group_user')
    #             if base_group.id not in groups:
    #                 groups.append(base_group.id)
    #
    #             # ✅ ASSIGN GROUPS
    #             # user.sudo().write({
    #             #     'groups_id': [(6, 0, groups)]
    #             # })
    #
    #             # Assign groups WITHOUT removing existing ones
    #             for group_id in groups:
    #                 user.sudo().write({
    #                     'groups_id': [(4, group_id)]
    #                 })
    #
    #             # ✅ SEND INVITE
    #             # user.sudo().action_reset_password()
    #
    #             # ✅ Generate signup token + URL
    #             # ✅ Send reset password email (generates token)
    #             user.sudo().action_reset_password()
    #
    #             # ✅ Get base URL
    #             base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #
    #             # ✅ Get database name
    #             db_name = self.env.cr.dbname
    #
    #             # ✅ Build SAME link as Odoo email
    #             invite_url = f"{base_url}/web/reset_password?db={db_name}&token={partner.signup_token}"
    #
    #             # ✅ SAVE RESULT
    #             rec.write({
    #                 'user_id': user.id,
    #                 'partner_id': partner.id,
    #                 'message': f'<strong>An invitation email containing the following link has been sent:</strong><br/>'
    #                            f'<a href="{invite_url}" target="_blank"><strong>{invite_url}</strong></a>',
    #                 'invite_url': invite_url,
    #                 'state': 'created',
    #             })
    #
    #             # # ✅ SAVE RESULT
    #             # rec.write({
    #             #     'user_id': user.id,
    #             #     'partner_id': partner.id,
    #             #     'state': 'created',
    #             #     'message': '✅ User created successfully and invitation sent'
    #             # })
    #
    #         except Exception as e:
    #             rec.write({
    #                 'state': 'error',
    #                 'message': f'❌ Error: {str(e)}'
    #             })

    def action_create_user(self):
        for rec in self:

            # 1. Check if user already exists
            existing_user = self.env['res.users'].sudo().search([
                ('login', '=', rec.email)
            ], limit=1)

            if existing_user:
                rec.write({
                    'user_id': existing_user.id,
                    'partner_id': existing_user.partner_id.id,
                    'state': 'error',
                    'message': 'User already exists with this email'
                })
                continue

            # 2. Create or reuse partner
            partner = self.env['res.partner'].sudo().search([
                ('email', '=', rec.email)
            ], limit=1)

            if not partner:
                partner = self.env['res.partner'].sudo().create({
                    'name': rec.name,
                    'email': rec.email,
                    'phone': rec.phone,
                })

            # 3. Create user (ONLY HERE)
            user = self.env['res.users'].sudo().create({
                'name': rec.name,
                'login': rec.email,
                'email': rec.email,
                'partner_id': partner.id,
                'active': True,
            })

            # 4. Assign roles
            groups = rec.role_ids.ids if rec.role_ids else []

            base_group = self.env.ref('base.group_user')
            if base_group.id not in groups:
                groups.append(base_group.id)

            # user.write({'groups_id': [(6, 0, groups)]})

            for group_id in groups:
                user.write({
                    'groups_id': [(4, group_id)]
                })

            # 5. Send invite
            user.sudo().action_reset_password()

            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            db_name = self.env.cr.dbname

            invite_url = f"{base_url}/web/reset_password?db={db_name}&token={partner.signup_token}"

            # 6. Save result
            rec.write({
                'user_id': user.id,
                'partner_id': partner.id,
                'invite_url': invite_url,
                'message': f'<strong>Invitation link:</strong><br/><a href="{invite_url}" target="_blank">{invite_url}</a>',
                'state': 'created',
            })

    def action_update_user(self):
        for rec in self:
            try:
                if not rec.user_id:
                    raise UserError("No user linked to update")

                # ✅ Update partner
                rec.partner_id.sudo().write({
                    'name': rec.name,
                    'email': rec.email,
                    'phone': rec.phone,
                })

                # ✅ Update user
                rec.user_id.sudo().write({
                    'name': rec.name,
                    'login': rec.email,
                    'email': rec.email,
                })

                # ✅ Update roles
                groups = rec.role_ids.ids if rec.role_ids else []

                base_group = self.env.ref('base.group_user')
                if base_group.id not in groups:
                    groups.append(base_group.id)

                # rec.user_id.sudo().write({
                #     'groups_id': [(6, 0, groups)]
                # })

                for group_id in groups:
                    rec.user_id.sudo().write({
                        'groups_id': [(4, group_id)]
                    })

                # ✅ Update state/message
                rec.write({
                    'state': 'created',
                    'message': '✏️ User updated successfully'
                })

            except Exception as e:
                rec.write({
                    'state': 'error',
                    'message': f'❌ Update failed: {str(e)}'
                })

    def unlink(self):
        for rec in self:
            if rec.user_id:
                try:
                    # OPTION A (SAFE): deactivate
                    rec.user_id.sudo().write({'active': False})

                    # OPTION B (DANGEROUS): delete completely
                    # rec.user_id.sudo().unlink()

                except Exception as e:
                    raise UserError(f"Cannot delete linked user: {str(e)}")

        return super(ServiceRequestUser, self).unlink()

    def action_clear_message(self):
        for rec in self:
            rec.message = False

    def action_reset_invite_link(self):
        for rec in self:
            if not rec.user_id:
                raise UserError("No user to reset password for.")

            # ✅ Generate new reset password token
            rec.user_id.sudo().action_reset_password()

            # ✅ Build new link
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            db_name = self.env.cr.dbname

            invite_url = f"{base_url}/web/reset_password?db={db_name}&token={rec.partner_id.signup_token}"

            # ✅ Update message + link
            rec.write({
                'invite_url': invite_url,
                'message': f'<strong>Password reset link regenerated:</strong><br/>'
                           f'<a href="{invite_url}" target="_blank"><strong>{invite_url}</strong></a>',
                'state': 'created',
            })
