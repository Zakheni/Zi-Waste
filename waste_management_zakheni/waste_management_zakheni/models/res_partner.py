"""Partner and related master-data extensions for waste customers."""
from odoo import models, fields, api, _
from odoo.exceptions import (ValidationError)
from odoo.exceptions import UserError, AccessDenied, ValidationError
import re

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'


class ResPartner(models.Model):
    """Customer validation, portal flags, and waste-specific fields."""
    _inherit = 'res.partner'


    pickup_point_ids = fields.One2many(
        'pickup.point', 'partner_id', string='Pickup Points'
    )

    wmz_use_company_config = fields.Boolean(
        string="Use Company Service Configuration",
        default=True,
        help="If enabled, this customer inherits services/container types from the company."
    )

    wmz_service_ids = fields.Many2many(
        "service.request",
        "wmz_partner_service_rel",
        "partner_id",
        "service_id",
        string="Waste Services for Company",
        help="Service offerings this client company uses."
    )

    wmz_container_type_ids = fields.Many2many(
        "container.type",
        "wmz_partner_container_type_rel",
        "partner_id",
        "container_type_id",
        string="Container Types for Company",
        help="Container types (Bins/Tanks) this client company uses."
    )

    wmz_waste_type_ids = fields.Many2many(
        "waste.type",
        "wmz_partner_waste_type_rel",
        "partner_id",
        "waste_type_id",
        string="Waste Types for Company",
        help="Waste types this company collected."
    )

    # company_id = fields.Many2one(
    #     'res.company',
    #     string='Company',
    #     required=False,
    #     default=lambda self: self.env.company,
    #     index=True
    # )
    # company_id = fields.Many2one(
    #     'res.company',
    #     string='Company',
    #     required=False,
    #     default=lambda self: self.env.company,
    #     index=True
    # )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        index=True,
        default=lambda self: self.env.company,
        help="Operating company that owns this contact record (POPIA isolation).",
    )

    parent_id = fields.Many2one(
        string='Company',
        domain="['&', ('id', '!=', id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    customer_reference = fields.Char(
        string="Customer Reference",
        copy=False,
        index=True,
        default="/",
        help="Unique customer identifier. Auto-generated on save when left empty.",
    )

    def _needs_customer_reference(self):
        """Return True when this partner still needs a generated reference."""
        self.ensure_one()
        return not self.customer_reference or self.customer_reference == '/'

    def _next_customer_reference(self):
        """Return the next value from the global customer reference sequence."""
        return self.env['ir.sequence'].sudo().next_by_code('customer.reference')

    def _assign_customer_reference(self, vals):
        """Fill customer_reference from sequence when missing or placeholder."""
        if vals.get('customer_reference') not in (False, None, '', '/'):
            return vals
        vals = dict(vals)
        vals['customer_reference'] = self._next_customer_reference()
        return vals

    def _write_missing_customer_references(self, vals):
        """Assign references before write when existing records still have '/'."""
        missing = self.filtered(
            lambda p: not p.customer_reference or p.customer_reference == '/'
        )
        if not missing:
            return super().write(vals)

        result = True
        for partner in missing:
            partner_vals = partner._assign_customer_reference(dict(vals))
            result = super(ResPartner, partner).write(partner_vals) and result

        others = self - missing
        if others and vals:
            result = super(ResPartner, others).write(vals) and result
        return result

    @api.model
    def _backfill_missing_customer_references(self):
        """Assign references to legacy partners that still have '/' or no value."""
        partners = self.with_context(active_test=False).search([
            '|', ('customer_reference', '=', False),
            ('customer_reference', 'in', ['/', '']),
        ])
        for partner in partners:
            partner.write({'customer_reference': partner._next_customer_reference()})
        return len(partners)

    @api.model
    def _wmz_system_partner_ids(self):
        """Return partner IDs that must remain globally readable (OdooBot, etc.)."""
        ids = set()
        for xmlid in ('base.partner_root', 'base.public_partner'):
            partner = self.env.ref(xmlid, raise_if_not_found=False)
            if partner:
                ids.add(partner.id)
        return list(ids)

    @api.model
    def _wmz_fix_system_partner_companies(self):
        """Reset system partners to company_id=False and apply POPIA base rule overrides."""
        Partner = self.sudo().with_context(active_test=False)
        for partner_id in self._wmz_system_partner_ids():
            partner = Partner.browse(partner_id)
            if partner.exists() and partner.company_id:
                partner.write({'company_id': False})

        partner_rule = self.env.ref('base.res_partner_rule', raise_if_not_found=False)
        if partner_rule:
            partner_rule.write({
                'name': 'res.partner company (POPIA strict)',
                'domain_force': (
                    "['|', '|', "
                    "('id', '=', user.partner_id.id), "
                    "('company_id', 'in', company_ids), "
                    "('company_id', '=', False)]"
                ),
            })

        users_rule = self.env.ref('base.res_users_rule', raise_if_not_found=False)
        if users_rule:
            users_rule.write({
                'name': 'user rule (POPIA strict)',
                'domain_force': (
                    "['|', '|', "
                    "('id', '=', user.id), "
                    "('company_id', 'in', company_ids), "
                    "('company_id', '=', False)]"
                ),
            })

        odoobot_ids = self._wmz_system_partner_ids()
        if odoobot_ids:
            odoobot_clause = f"('id', 'in', {odoobot_ids})"
            wmz_partner_domain = (
                "['|', '|', '|', "
                "('id', '=', user.partner_id.id), "
                "('company_id', 'in', user.company_ids.ids), "
                "('company_id', '=', False), "
                f"{odoobot_clause}]"
            )
            for xmlid in (
                'waste_management_zakheni.wmz_res_partner_company_rule',
                'waste_management_zakheni.partner_company_rule',
            ):
                rule = self.env.ref(xmlid, raise_if_not_found=False)
                if rule:
                    rule.write({'domain_force': wmz_partner_domain})

        return True

    @api.model
    def _backfill_missing_company_ids(self):
        """Assign company_id on legacy partners/users for POPIA isolation."""
        Partner = self.env['res.partner'].sudo().with_context(active_test=False)
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        system_partner_ids = set(self._wmz_system_partner_ids())
        updated = 0

        for user in Users.search([]):
            if not user.company_id or not user.partner_id:
                continue
            partner = user.partner_id
            if partner.id in system_partner_ids:
                continue
            if partner.company_id != user.company_id:
                partner.write({'company_id': user.company_id.id})
                updated += 1

        for company in self.env['res.company'].sudo().search([]):
            if company.partner_id and company.partner_id.company_id != company:
                company.partner_id.write({'company_id': company.id})
                updated += 1

        for partner in Partner.search([('company_id', '=', False), ('parent_id', '!=', False)]):
            parent_company = partner.parent_id.company_id
            if parent_company:
                partner.write({'company_id': parent_company.id})
                updated += 1

        if 'waste.service.request' in self.env:
            Request = self.env['waste.service.request'].sudo()
            for partner in Partner.search([('company_id', '=', False)]):
                request = Request.search(
                    [('partner_id', '=', partner.id), ('company_id', '!=', False)],
                    limit=1,
                    order='id desc',
                )
                if request:
                    partner.write({'company_id': request.company_id.id})
                    updated += 1

        for partner in Partner.search([('parent_id', '!=', False)]):
            parent = partner.parent_id
            if not parent.company_id or not partner.company_id:
                continue
            if parent.company_id != partner.company_id:
                partner.write({'parent_id': False})
                updated += 1

        return updated

    @api.model
    def _wmz_contacts_domain_list(self):
        """Server-side Contacts domain (POPIA-aligned, user-specific)."""
        user = self.env.user
        company_ids = user.company_ids.ids
        company_partner_ids = user.company_ids.partner_id.ids
        return [
            "|",
            "|",
            "|",
            ("id", "=", user.partner_id.id),
            ("company_id", "in", company_ids),
            ("company_id", "=", False),
            ("id", "in", company_partner_ids),
        ]

    @api.model
    def _wmz_fix_contacts_action_domain(self):
        """Store a web-client-safe fallback domain on the Contacts action."""
        action = self.env.ref("contacts.action_contacts", raise_if_not_found=False)
        if not action:
            return True
        domain = "[('company_id', 'in', allowed_company_ids)]"
        if action.domain != domain:
            action.sudo().write({"domain": domain})
        return True

    @api.constrains('company_id')
    def _check_wmz_company_id_required(self):
        """Every customer/contact must belong to a company to stay visible under POPIA rules."""
        for partner in self:
            if not partner._wmz_requires_company_id():
                continue
            if not partner.company_id:
                raise ValidationError(_(
                    "Company is required on contacts. Select your operating company "
                    "so this customer remains visible to your organisation."
                ))

    @api.constrains('parent_id', 'company_id')
    def _check_parent_same_company(self):
        """POPIA: parent company contact must belong to the same Odoo company."""
        for partner in self:
            parent = partner.parent_id
            if not parent or not parent.company_id or not partner.company_id:
                continue
            if parent.company_id != partner.company_id:
                raise ValidationError(_(
                    "The linked company contact must belong to the same company as this contact."
                ))

    def _wmz_default_company_id(self, vals):
        """Resolve company_id for new partners without breaking user-linked records."""
        if vals.get('company_id'):
            return vals['company_id']
        if vals.get('parent_id'):
            parent = self.env['res.partner'].browse(vals['parent_id'])
            if parent.company_id:
                return parent.company_id.id
        return self.env.company.id

    def _wmz_requires_company_id(self):
        """Return True when this partner must have company_id for POPIA visibility."""
        self.ensure_one()
        if self.id in self._wmz_system_partner_ids():
            return False
        return True

    def _wmz_internal_user_company_id(self):
        """Return the single company of linked internal users, if unambiguous."""
        self.ensure_one()
        internal_users = self.user_ids.filtered(lambda user: not user.share)
        companies = internal_users.mapped('company_id')
        if len(companies) == 1:
            return companies.id
        return False


    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete Contacts."))
        return super().unlink()

    phone = fields.Char(required=True)
    email = fields.Char(required=True)
    # mobile = fields.Char(required=True)

    role_ids = fields.Many2many(
        'res.groups',
        string="Roles",
        domain=[
            ('category_id.name', 'in', [
                'Client Portal',
            ])
        ],

        tracking=True
    )

    invite_url = fields.Char(string="Portal Invitation Link", readonly=True)
    invite_message = fields.Html(string="Invitation Message", readonly=True)
    # ------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        """Default operating company for multi-company isolation."""
        res = super().default_get(fields_list)
        if 'company_id' in fields_list and not res.get('company_id'):
            res['company_id'] = self.env.company.id
        return res

    @api.onchange('parent_id')
    def _onchange_wmz_parent_id_company(self):
        """Inherit company from linked company contact."""
        if self.parent_id and self.parent_id.company_id:
            self.company_id = self.parent_id.company_id

    @api.model_create_multi
    def create(self, vals_list):
        """Apply waste-specific defaults when creating partners."""
        prepared = []
        for vals in vals_list:
            if not vals.get('company_id'):
                vals['company_id'] = self._wmz_default_company_id(vals)
            if vals.get('phone'):
                vals['phone'] = self._normalize_phone(vals['phone'])
            if vals.get('mobile'):
                vals['mobile'] = self._normalize_phone(vals['mobile'])
            prepared.append(self._assign_customer_reference(vals))

        partners = super().create(prepared)

        for partner in partners.filtered(lambda p: p._needs_customer_reference()):
            partner.sudo().write({
                'customer_reference': partner._next_customer_reference(),
            })

        partners._sync_roles_to_users()

        return partners

    # ------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------

    def write(self, vals):
        """Validate partner fields on update."""
        vals = dict(vals)
        if 'parent_id' in vals and 'company_id' not in vals:
            parent_id = vals.get('parent_id')
            if parent_id:
                parent = self.env['res.partner'].browse(parent_id)
                if parent.company_id:
                    vals['company_id'] = parent.company_id.id
            elif len(self) == 1:
                user_company_id = self._wmz_internal_user_company_id()
                if user_company_id:
                    vals['company_id'] = user_company_id

        if vals.get('company_id') is False:
            vals.pop('company_id')

        if vals.get('phone'):
            vals['phone'] = self._normalize_phone(vals['phone'])
        if vals.get('mobile'):
            vals['mobile'] = self._normalize_phone(vals['mobile'])

        res = self._write_missing_customer_references(vals)

        if 'role_ids' in vals:
            self._ensure_portal_user()
            self._sync_roles_to_users()

        return res

    # ------------------------------------------------------------
    # DELETE RESTRICTION
    # ------------------------------------------------------------

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete Contacts."))
        return super().unlink()

    # ------------------------------------------------------------
    # ROLE SYNC LOGIC (🔥 CORE)
    # ------------------------------------------------------------

    def _sync_roles_to_users(self):
        portal_group = self.env.ref('base.group_portal')

        client_groups = self.env['res.groups'].search([
            ('category_id.name', '=', 'Client Portal')
        ])

        for partner in self:
            for user in partner.user_ids:
                user = user.sudo()  # ✅ bypass access rights

                commands = []

                # 1. Remove old Client Management roles
                commands += [(3, g.id) for g in client_groups]

                # 2. Add selected roles
                commands += [(4, g.id) for g in partner.role_ids]

                # 3. Ensure portal access
                if partner.role_ids:
                    commands.append((4, portal_group.id))

                user.write({'groups_id': commands})

    def action_send_portal_reset(self):
        for partner in self:

            # ❌ Must have email
            if not partner.email:
                raise ValidationError(_("Partner must have an email."))

            # ✅ Ensure portal user exists
            partner._ensure_portal_user()

            user = partner.user_ids[:1]

            if not user:
                raise ValidationError(_("No user linked to this partner."))

            # ✅ Send reset password (generates token)
            user.sudo().action_reset_password()

            # ✅ Build link
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            db_name = self.env.cr.dbname

            invite_url = f"{base_url}/web/reset_password?db={db_name}&token={partner.signup_token}"

            # ✅ Save message
            partner.write({
                'invite_url': invite_url,
                'invite_message': f"""
                    <div>
                        <strong>Password reset link:</strong><br/>
                        <a href="{invite_url}" target="_blank">{invite_url}</a>
                    </div>
                """
            })

    def action_clear_invite(self):
        for rec in self:
            rec.write({
                'invite_url': False,
                'invite_message': False,
            })
    # ------------------------------------------------------------
    # AUTO CREATE PORTAL USER (🔥 IMPORTANT)
    # ------------------------------------------------------------

    # def _ensure_portal_user(self):
    #     portal_group = self.env.ref('base.group_portal')
    #
    #     for partner in self:
    #         if not partner.user_ids and partner.email:
    #             self.env['res.users'].sudo().create({
    #                 'name': partner.name,
    #                 'login': partner.email,
    #                 'partner_id': partner.id,
    #                 'groups_id': [(6, 0, [portal_group.id])]
    #             })

    def _ensure_portal_user(self):
        portal_group = self.env.ref('base.group_portal')

        for partner in self:
            if partner.user_ids:
                continue  # ✅ already has user, skip

            if partner.email:
                self.env['res.users'].sudo().create({
                    'name': partner.name,
                    'login': partner.email,
                    'partner_id': partner.id,
                    'groups_id': [(6, 0, [portal_group.id])]
                })


    # ------------------------------------------------------------
    # Helper: normalize phone numbers
    # ------------------------------------------------------------
    def _normalize_phone(self, value):
        """
        Normalize phone numbers by removing spaces, dashes, and brackets.

        +27 12 345 6789  → +27123456789
        (+27)12-345-6789 → +27123456789
        """
        if not value:
            return value
        return re.sub(r'[\s\-\(\)]+', '', value)

    # ------------------------------------------------------------
    # CREATE: normalize BEFORE constraint
    # ------------------------------------------------------------
    # @api.model_create_multi
    # def create(self, vals_list):
    #     for vals in vals_list:
    #         if vals.get('phone'):
    #             vals['phone'] = self._normalize_phone(vals['phone'])
    #         if vals.get('mobile'):
    #             vals['mobile'] = self._normalize_phone(vals['mobile'])
    #     return super().create(vals_list)
    #
    # # ------------------------------------------------------------
    # # WRITE: normalize BEFORE constraint
    # # ------------------------------------------------------------
    # def write(self, vals):
    #     if vals.get('phone'):
    #         vals['phone'] = self._normalize_phone(vals['phone'])
    #     if vals.get('mobile'):
    #         vals['mobile'] = self._normalize_phone(vals['mobile'])
    #     return super().write(vals)

    # ------------------------------------------------------------
    # CONSTRAINT: validate normalized value ONLY
    # ------------------------------------------------------------
    @api.constrains('phone', 'mobile')
    def _check_phone_country_code(self):
        for partner in self:
            for field in ('phone', 'mobile'):
                value = partner[field]
                if not value:
                    continue

                if not re.match(r'^\+\d{7,15}$', value):
                    raise ValidationError(
                         _("Phone number must include country code, e.g. +27 12 345 6789, (+27)12-345-6789 and +27123456789 ✅ "
                          "\n and it must not include Alpha numeric ❌ ")
                    )

    @api.constrains('email')
    def _check_email_required(self):
        for partner in self:
            # Skip contacts that are not real business partners
            if partner.is_company or partner.customer_rank > 0 or partner.supplier_rank > 0:
                if not partner.email:
                    raise ValidationError(
                        _("Email address is required. ⚠️")
                    )

    @api.constrains('email')
    def _check_email_format(self):
        for partner in self:
            if partner.email:
                email = partner.email.strip()
                if not re.match(EMAIL_REGEX, email):
                    raise ValidationError(
                        _("Invalid work email address format e.g email must take this format ✅'email@example.com' not this ❌ %s ") % email

                    )




class ResPartnerCategory(models.Model):
    """Partner category extensions."""
    _inherit = "res.partner.category"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner category."))
        return super().unlink()


class ResPartnerTitleCategory(models.Model):
    """Partner title category extensions."""
    _inherit = "res.partner.title"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner tittle."))
        return super().unlink()


class ResPartnerTitleIndustry(models.Model):
    """Partner title industry extensions."""
    _inherit = "res.partner.industry"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner industry."))
        return super().unlink()


class ResCountry(models.Model):
    """Country extensions for waste module."""
    _inherit = "res.country"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner country."))
        return super().unlink()


class ResCountryState(models.Model):
    """State/province extensions for waste module."""
    _inherit = "res.country.state"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner state."))
        return super().unlink()


class ResCountryGroup(models.Model):
    """Country group extensions for waste module."""
    _inherit = "res.country.group"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner group."))
        return super().unlink()


class ResBank(models.Model):
    """Bank extensions for waste module."""
    _inherit = "res.bank"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete bank."))
        return super().unlink()


# class ResPartnerBank(models.Model):
#     _inherit = "res.partner.bank"
#
#     def unlink(self):
#         if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
#             raise UserError(_("You are not allowed to delete partner bank."))
#         return super().unlink()
