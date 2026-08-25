"""Company-scoped backend user provisioning for Waste Management governance."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

# Groups shown on Waste Management → Users (must match security/waste_groups.xml
# and security/wmz_user_form_groups.xml — hidden category, short labels).
WMZ_OPERATIONS_GROUP_XMLIDS = (
    'waste_management_zakheni.group_wmz_manager',
    'waste_management_zakheni.group_wmz_admin_clerk',
    'waste_management_zakheni.group_wmz_driver',
    'waste_management_zakheni.group_wmz_finance',
    'waste_management_zakheni.group_wmz_provider',
    'waste_management_zakheni.group_wmz_user_manager',
    'waste_management_zakheni.group_wmz_admin',
)
PASTEL_GROUP_XMLIDS = (
    'pastel_connector.group_pastel_connector_user',
    'pastel_connector.group_pastel_connector_manager',
)
SAGE_GROUP_XMLIDS = (
    'sage_connector.group_sage_user',
    'sage_connector.group_sage_manager',
)
VEHICLE_GROUP_XMLIDS = (
    'vehicle_inspection.group_vehicle_inspection_user',
    'vehicle_inspection.group_vehicle_inspection_manager',
)
FLEET_GROUP_XMLIDS = (
    'fleet.fleet_group_user',
    'fleet.fleet_group_manager',
)
WMZ_USER_FORM_GROUP_XMLIDS = (
    WMZ_OPERATIONS_GROUP_XMLIDS + SAGE_GROUP_XMLIDS + VEHICLE_GROUP_XMLIDS + FLEET_GROUP_XMLIDS
)

PRIVILEGED_GROUP_XMLIDS = (
    'waste_management_zakheni.group_wmz_admin',
    'waste_management_zakheni.group_central_admin',
    'base.group_system',
    'base.group_erp_manager',
)


class WmzUserProvision(models.Model):
    """Provision and manage backend users within allowed companies (POPIA-scoped)."""

    _name = 'wmz.service.request.user'
    _description = 'WMZ User Provisioning'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    service_request_id = fields.Many2one('waste.service.request')

    name = fields.Char(required=True, tracking=True)
    email = fields.Char(required=True, tracking=True, string='Login (Email)')
    phone = fields.Char(tracking=True)
    image_1920 = fields.Image(
        string='Photo',
        max_width=1920,
        max_height=1920,
    )
    avatar_128 = fields.Image(
        string='Avatar',
        related='image_1920',
        max_width=128,
        max_height=128,
        store=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='Deactivate to block login without deleting the user record.',
    )

    last_login = fields.Datetime(
        string='Last Login',
        related='user_id.login_date',
        readonly=True,
    )
    is_online = fields.Boolean(compute='_compute_online')
    lang = fields.Selection(related='user_id.lang', string='Language', readonly=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    company_ids = fields.Many2many(
        'res.company',
        related='user_id.company_ids',
        string='Allowed Companies',
        readonly=True,
    )
    wmz_can_edit_company = fields.Boolean(
        compute='_compute_wmz_can_edit_company',
    )

    status = fields.Selection(
        [('confirmed', 'Confirmed'), ('not_confirmed', 'Not Confirmed')],
        compute='_compute_status',
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('created', 'Created'), ('error', 'Error')],
        default='draft',
        tracking=True,
    )

    role_ids = fields.Many2many(
        'res.groups',
        'wmz_service_request_user_role_rel',
        'provision_id',
        'group_id',
        string='Operations Roles',
        required=True,
        tracking=True,
        help='Waste Management operational roles (Manager, Clerk, Driver, Finance, etc.).',
    )

    role_wmz_ids = fields.Many2many(
        'res.groups',
        'wmz_user_provision_wmz_group_rel',
        'provision_id',
        'group_id',
        string='Waste Management',
    )
    role_pastel_ids = fields.Many2many(
        'res.groups',
        'wmz_user_provision_pastel_group_rel',
        'provision_id',
        'group_id',
        string='Pastel Connector',
    )
    role_sage_ids = fields.Many2many(
        'res.groups',
        'wmz_user_provision_sage_group_rel',
        'provision_id',
        'group_id',
        string='Sage Connector',
    )
    role_vehicle_ids = fields.Many2many(
        'res.groups',
        'wmz_user_provision_vehicle_group_rel',
        'provision_id',
        'group_id',
        string='Vehicle Inspection',
    )
    role_fleet_ids = fields.Many2many(
        'res.groups',
        'wmz_user_provision_fleet_group_rel',
        'provision_id',
        'group_id',
        string='Fleet',
    )

    user_id = fields.Many2one('res.users', readonly=True, copy=False)
    partner_id = fields.Many2one('res.partner', readonly=True, copy=False)

    message = fields.Html(string='Status Message', readonly=True, sanitize=False)
    invite_url = fields.Char(string='Password Link', readonly=True)

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------

    @api.depends_context('uid')
    def _compute_wmz_can_edit_company(self):
        can_edit = self._can_manage_multiple_companies()
        for rec in self:
            rec.wmz_can_edit_company = can_edit

    def _compute_status(self):
        for rec in self:
            rec.status = 'confirmed' if rec.user_id and rec.user_id.login_date else 'not_confirmed'

    def _compute_online(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.last_login:
                rec.is_online = (now - rec.last_login).total_seconds() < 300
            else:
                rec.is_online = False

    @api.model
    def _groups_by_xmlids(self, xmlids):
        groups = self.env['res.groups']
        for xmlid in xmlids:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                groups |= group
        return groups

    @api.model
    def _role_groups_wmz(self):
        return self._groups_by_xmlids(WMZ_OPERATIONS_GROUP_XMLIDS)

    @api.model
    def _role_groups_pastel(self):
        return self._groups_by_xmlids(PASTEL_GROUP_XMLIDS)

    @api.model
    def _role_groups_sage(self):
        return self._groups_by_xmlids(SAGE_GROUP_XMLIDS)

    @api.model
    def _role_groups_vehicle(self):
        return self._groups_by_xmlids(VEHICLE_GROUP_XMLIDS)

    @api.model
    def _role_groups_fleet(self):
        return self._groups_by_xmlids(FLEET_GROUP_XMLIDS)

    def _apply_recommended_access_groups(self):
        """Align vehicle inspection / fleet rights with selected WMZ operational roles."""
        driver = self.env.ref('waste_management_zakheni.group_wmz_driver', raise_if_not_found=False)
        manager = self.env.ref('waste_management_zakheni.group_wmz_manager', raise_if_not_found=False)
        admin = self.env.ref('waste_management_zakheni.group_wmz_admin', raise_if_not_found=False)
        vi_user = self.env.ref('vehicle_inspection.group_vehicle_inspection_user', raise_if_not_found=False)
        vi_mgr = self.env.ref('vehicle_inspection.group_vehicle_inspection_manager', raise_if_not_found=False)
        fleet_user = self.env.ref('fleet.fleet_group_user', raise_if_not_found=False)
        fleet_mgr = self.env.ref('fleet.fleet_group_manager', raise_if_not_found=False)

        for rec in self:
            vehicle = rec.role_vehicle_ids
            fleet = rec.role_fleet_ids
            wmz = rec.role_wmz_ids
            if admin and admin in wmz:
                if vi_mgr:
                    vehicle |= vi_mgr
                if fleet_mgr:
                    fleet |= fleet_mgr
            else:
                if manager and manager in wmz and fleet_user:
                    fleet |= fleet_user
                if driver and driver in wmz and vi_user:
                    vehicle |= vi_user
            rec.with_context(wmz_syncing_roles=True).write({
                'role_vehicle_ids': [(6, 0, vehicle.ids)],
                'role_fleet_ids': [(6, 0, fleet.ids)],
            })

    def _refresh_role_ids_from_sections(self):
        for rec in self:
            rec.with_context(wmz_syncing_roles=True).write({
                'role_ids': [(6, 0, (
                    rec.role_wmz_ids | rec.role_sage_ids | rec.role_vehicle_ids | rec.role_fleet_ids
                ).ids)],
            })

    def _sync_sections_from_roles(self):
        wmz = self._role_groups_wmz()
        sage = self._role_groups_sage()
        vehicle = self._role_groups_vehicle()
        fleet = self._role_groups_fleet()
        for rec in self:
            rec.with_context(wmz_syncing_roles=True).write({
                'role_wmz_ids': [(6, 0, (rec.role_ids & wmz).ids)],
                'role_sage_ids': [(6, 0, (rec.role_ids & sage).ids)],
                'role_vehicle_ids': [(6, 0, (rec.role_ids & vehicle).ids)],
                'role_fleet_ids': [(6, 0, (rec.role_ids & fleet).ids)],
            })

    @api.model
    def action_migrate_role_sections(self):
        """Populate section checkboxes from existing role_ids (module upgrade).

        Maps legacy Pastel Connector rights onto Sage Connector groups when present.
        """
        records = self.search([])
        pastel_user = self.env.ref(
            'pastel_connector.group_pastel_connector_user', raise_if_not_found=False
        )
        pastel_mgr = self.env.ref(
            'pastel_connector.group_pastel_connector_manager', raise_if_not_found=False
        )
        sage_user = self.env.ref('sage_connector.group_sage_user', raise_if_not_found=False)
        sage_mgr = self.env.ref('sage_connector.group_sage_manager', raise_if_not_found=False)
        for rec in records:
            roles = rec.role_ids
            if pastel_mgr and pastel_mgr in roles and sage_mgr:
                roles |= sage_mgr
            elif pastel_user and pastel_user in roles and sage_user:
                roles |= sage_user
            if roles != rec.role_ids:
                rec.with_context(wmz_syncing_roles=True).write({
                    'role_ids': [(6, 0, roles.ids)],
                })
        records._sync_sections_from_roles()
        records._apply_recommended_access_groups()
        records._refresh_role_ids_from_sections()
        for rec in records.filtered('user_id'):
            rec._apply_managed_groups(rec.user_id, rec.role_ids)

    # -------------------------------------------------------------------------
    # Defaults & constraints
    # -------------------------------------------------------------------------

    def _sync_partner_image(self):
        for rec in self.filtered('partner_id'):
            rec.partner_id.sudo().write({'image_1920': rec.image_1920 or False})

    def _load_image_from_partner(self):
        for rec in self.filtered(lambda r: r.partner_id and not r.image_1920):
            rec.image_1920 = rec.partner_id.image_1920

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        creator = self.env.user
        if (
            'company_id' in fields_list
            and not res.get('company_id')
            and creator.company_id
            and not self._can_manage_multiple_companies(creator)
        ):
            res['company_id'] = creator.company_id.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._enforce_record_company(vals)
        records = super().create(vals_list)
        if not self.env.context.get('wmz_syncing_roles'):
            section_keys = ('role_wmz_ids', 'role_sage_ids', 'role_vehicle_ids', 'role_fleet_ids')
            if any(k in vals for vals in vals_list for k in section_keys):
                records._refresh_role_ids_from_sections()
            else:
                records._sync_sections_from_roles()
            if any('role_wmz_ids' in vals for vals in vals_list):
                records._apply_recommended_access_groups()
                records._refresh_role_ids_from_sections()
        for rec in records:
            rec._validate_assignable_roles(rec.role_ids)
        records._load_image_from_partner()
        return records

    def write(self, vals):
        if 'company_id' in vals:
            self._enforce_record_company(vals)
        res = super().write(vals)
        if not self.env.context.get('wmz_syncing_roles'):
            if any(k in vals for k in ('role_wmz_ids', 'role_sage_ids', 'role_vehicle_ids', 'role_fleet_ids')):
                self._refresh_role_ids_from_sections()
            elif 'role_ids' in vals:
                self._sync_sections_from_roles()
            if 'role_wmz_ids' in vals:
                self._apply_recommended_access_groups()
                self._refresh_role_ids_from_sections()
        if 'role_ids' in vals:
            for rec in self:
                rec._validate_assignable_roles(rec.role_ids)
        if 'active' in vals and self.user_id:
            self.user_id.sudo().write({'active': vals['active']})
        if 'image_1920' in vals:
            self._sync_partner_image()
        return res

    def unlink(self):
        for rec in self:
            if rec.user_id:
                rec.user_id.sudo().write({'active': False})
        return super().unlink()

    # -------------------------------------------------------------------------
    # Governance helpers
    # -------------------------------------------------------------------------

    @api.model
    def _can_manage_multiple_companies(self, user=None):
        user = user or self.env.user
        return user.has_group('base.group_system') or user.has_group(
            'waste_management_zakheni.group_central_admin'
        ) or user.has_group('waste_management_zakheni.group_wmz_admin')

    @api.model
    def _enforce_record_company(self, vals):
        if self._can_manage_multiple_companies():
            return
        creator = self.env.user
        if creator.company_id:
            vals['company_id'] = creator.company_id.id

    @api.model
    def _managed_groups(self):
        return self._groups_by_xmlids(WMZ_USER_FORM_GROUP_XMLIDS)

    @api.model
    def _privileged_groups(self):
        groups = self.env['res.groups']
        for xmlid in PRIVILEGED_GROUP_XMLIDS:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                groups |= group
        return groups

    def _validate_assignable_roles(self, role_ids):
        if self._can_manage_multiple_companies():
            return
        forbidden = role_ids & self._privileged_groups()
        if forbidden:
            raise ValidationError(_(
                'Company Administrators cannot assign platform-level roles: %s'
            ) % ', '.join(forbidden.mapped('display_name')))

    def _check_manage_target_user(self):
        self.ensure_one()
        creator = self.env.user
        if self._can_manage_multiple_companies(creator):
            return
        if self.company_id not in creator.company_ids:
            raise UserError(_('You can only manage users in your own company.'))

    def _build_reset_link(self, partner):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        db_name = self.env.cr.dbname
        token = partner.sudo().signup_token
        return f'{base_url}/web/reset_password?db={db_name}&token={token}'

    def _apply_managed_groups(self, user, role_ids):
        """Replace managed operational groups while preserving unrelated access groups."""
        managed = self._managed_groups()
        base_user = self.env.ref('base.group_user')
        new_groups = (user.groups_id - managed) | role_ids | base_user
        user.sudo().write({'groups_id': [(6, 0, new_groups.ids)]})

    def _get_or_create_partner(self):
        self.ensure_one()
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('email', '=', self.email)], limit=1)
        if not partner:
            partner = Partner.create({
                'name': self.name,
                'email': self.email,
                'phone': self.phone,
                'company_id': self.company_id.id,
                'image_1920': self.image_1920,
            })
        else:
            partner.write({
                'name': self.name,
                'phone': self.phone,
                'company_id': self.company_id.id,
                'image_1920': self.image_1920 or partner.image_1920,
            })
        return partner

    # -------------------------------------------------------------------------
    # User actions
    # -------------------------------------------------------------------------

    def action_create_user(self):
        for rec in self:
            try:
                rec._check_manage_target_user()
                rec._validate_assignable_roles(rec.role_ids)

                existing = self.env['res.users'].sudo().search([
                    ('login', '=', rec.email),
                ], limit=1)
                if existing:
                    rec.write({
                        'user_id': existing.id,
                        'partner_id': existing.partner_id.id,
                        'state': 'error',
                        'message': _('A user with this login already exists.'),
                    })
                    continue

                partner = rec._get_or_create_partner()
                user = self.env['res.users'].sudo().create({
                    'name': rec.name,
                    'login': rec.email,
                    'email': rec.email,
                    'partner_id': partner.id,
                    'company_id': rec.company_id.id,
                    'company_ids': [(6, 0, [rec.company_id.id])],
                    'active': rec.active,
                })
                rec._apply_managed_groups(user, rec.role_ids)
                user.sudo().with_context(create_user=True).action_reset_password()
                invite_url = rec._build_reset_link(partner)

                rec.write({
                    'user_id': user.id,
                    'partner_id': partner.id,
                    'invite_url': invite_url,
                    'message': _(
                        '<strong>User created.</strong> Password setup link:<br/>'
                        '<a href="%s" target="_blank">%s</a>'
                    ) % (invite_url, invite_url),
                    'state': 'created',
                })
            except (UserError, ValidationError) as err:
                rec.write({'state': 'error', 'message': str(err)})
            except Exception as err:
                rec.write({'state': 'error', 'message': _('Error: %s') % err})

    def action_update_user(self):
        for rec in self:
            try:
                if not rec.user_id:
                    raise UserError(_('No linked user to update. Create the user first.'))
                rec._check_manage_target_user()
                rec._validate_assignable_roles(rec.role_ids)

                user = rec.user_id.sudo()
                rec.partner_id.sudo().write({
                    'name': rec.name,
                    'email': rec.email,
                    'phone': rec.phone,
                    'company_id': rec.company_id.id,
                    'image_1920': rec.image_1920 or rec.partner_id.image_1920,
                })
                user.write({
                    'name': rec.name,
                    'login': rec.email,
                    'email': rec.email,
                    'active': rec.active,
                    'company_id': rec.company_id.id,
                    'company_ids': [(6, 0, [rec.company_id.id])],
                })
                rec._apply_managed_groups(user, rec.role_ids)
                rec.write({
                    'state': 'created',
                    'message': _('User profile and roles updated successfully.'),
                })
            except (UserError, ValidationError) as err:
                rec.write({'state': 'error', 'message': str(err)})
            except Exception as err:
                rec.write({'state': 'error', 'message': _('Update failed: %s') % err})

    def action_reset_invite_link(self):
        for rec in self:
            if not rec.user_id:
                raise UserError(_('No linked user. Create the user first.'))
            rec._check_manage_target_user()
            rec.user_id.sudo().action_reset_password()
            invite_url = rec._build_reset_link(rec.partner_id)
            rec.write({
                'invite_url': invite_url,
                'message': _(
                    '<strong>Password reset link sent.</strong><br/>'
                    '<a href="%s" target="_blank">%s</a>'
                ) % (invite_url, invite_url),
                'state': 'created',
            })

    def action_open_change_password(self):
        self.ensure_one()
        if not self.user_id:
            raise UserError(_('No linked user. Create the user first.'))
        self._check_manage_target_user()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Change Password'),
            'res_model': 'wmz.user.password.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_provision_id': self.id,
                'default_user_id': self.user_id.id,
                'default_login': self.email,
            },
        }

    def action_clear_message(self):
        self.write({'message': False, 'invite_url': False})
