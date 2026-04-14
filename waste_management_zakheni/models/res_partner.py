from odoo import models, fields, api, _
from odoo.exceptions import (ValidationError)
from odoo.exceptions import UserError, AccessDenied, ValidationError
import re

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'


class ResPartner(models.Model):
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

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=False,
        default=lambda self: self.env.company,
        index=True
    )
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
        index=True
    )


    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete Contacts."))
        return super().unlink()

    phone = fields.Char(required=True)
    email = fields.Char(required=True)
    # mobile = fields.Char(required=True)


    role = fields.Selection([
        ('customer', 'Customer'),
        ('agent', 'Agent'),
    ], string="Role", tracking=True)

    invite_url = fields.Char(string="Portal Invitation Link", readonly=True)
    invite_message = fields.Html(string="Invitation Message", readonly=True)
    # ------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('phone'):
                vals['phone'] = self._normalize_phone(vals['phone'])
            if vals.get('mobile'):
                vals['mobile'] = self._normalize_phone(vals['mobile'])

        partners = super().create(vals_list)

        # ✅ Ensure portal user + sync roles
        # partners._ensure_portal_user()
        partners._sync_roles_to_users()

        return partners

    # ------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------

    def write(self, vals):
        if vals.get('phone'):
            vals['phone'] = self._normalize_phone(vals['phone'])
        if vals.get('mobile'):
            vals['mobile'] = self._normalize_phone(vals['mobile'])

        res = super().write(vals)

        if 'role' in vals:
            # self._ensure_portal_user()
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

        group_customer = self.env.ref('waste_management_zakheni.group_wmz_client_customer')
        group_agent = self.env.ref('waste_management_zakheni.group_wmz_client_agent')

        for partner in self:
            for user in partner.user_ids:
                user = user.sudo()

                commands = []

                # ❌ Remove ONLY your custom groups
                commands += [(3, group_customer.id)]
                commands += [(3, group_agent.id)]

                # ✅ Assign based on role
                if partner.role == 'customer':
                    commands.append((4, group_customer.id))

                elif partner.role == 'agent':
                    commands.append((4, group_agent.id))

                user.write({'groups_id': commands})

    def action_send_portal_reset(self):
        for partner in self:

            if not partner.email:
                raise ValidationError(_("Partner must have an email."))

            user = partner.user_ids[:1]

            # ✅ AUTO CREATE USER IF MISSING
            if not user:
                user = self.env['res.users'].sudo().create({
                    'name': partner.name,
                    'login': partner.email,
                    'email': partner.email,
                    'partner_id': partner.id,

                    # 🔥 FORCE PORTAL USER ONLY
                    'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]
                })

                # ✅ assign role groups immediately
                partner._sync_roles_to_users()

            # ✅ Send reset password
            user.sudo().action_reset_password()

            # ✅ Build link
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            db_name = self.env.cr.dbname

            invite_url = f"{base_url}/web/reset_password?db={db_name}&token={partner.signup_token}"

            partner.write({
                'invite_url': invite_url,
                'invite_message': f"""
                    <div>
                        <strong>Password reset link:</strong><br/>
                        <a href="{invite_url}" target="_blank">{invite_url}</a>
                    </div>
                """
            })


    # def action_send_portal_reset(self):
    #     for partner in self:
    #
    #         # ❌ Must have email
    #         if not partner.email:
    #             raise ValidationError(_("Partner must have an email."))
    #
    #         # # ✅ Ensure portal user exists
    #         # partner._ensure_portal_user()
    #         #
    #         # user = partner.user_ids[:1]
    #         #
    #         # if not user:
    #         #     raise ValidationError(_("No user linked to this partner."))
    #
    #         user = partner.user_ids[:1]
    #
    #         if not user:
    #             raise ValidationError(
    #                 _("No user linked to this partner. Please create the user first from the Users module."))
    #
    #         # ✅ Send reset password (generates token)
    #         user.sudo().action_reset_password()
    #
    #         # ✅ Build link
    #         base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #         db_name = self.env.cr.dbname
    #
    #         invite_url = f"{base_url}/web/reset_password?db={db_name}&token={partner.signup_token}"
    #
    #         # ✅ Save message
    #         partner.write({
    #             'invite_url': invite_url,
    #             'invite_message': f"""
    #                 <div>
    #                     <strong>Password reset link:</strong><br/>
    #                     <a href="{invite_url}" target="_blank">{invite_url}</a>
    #                 </div>
    #             """
    #         })

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

    # def _ensure_portal_user(self):
    #     portal_group = self.env.ref('base.group_portal')
    #
    #     for partner in self:
    #         if partner.user_ids:
    #             continue  # ✅ already has user, skip
    #
    #         if partner.email:
    #             self.env['res.users'].sudo().create({
    #                 'name': partner.name,
    #                 'login': partner.email,
    #                 'partner_id': partner.id,
    #                 'groups_id': [(6, 0, [portal_group.id])]
    #             })



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
    _inherit = "res.partner.category"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner category."))
        return super().unlink()


class ResPartnerTitleCategory(models.Model):
    _inherit = "res.partner.title"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner tittle."))
        return super().unlink()


class ResPartnerTitleIndustry(models.Model):
    _inherit = "res.partner.industry"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner industry."))
        return super().unlink()


class ResCountry(models.Model):
    _inherit = "res.country"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner country."))
        return super().unlink()


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner state."))
        return super().unlink()


class ResCountryGroup(models.Model):
    _inherit = "res.country.group"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner group."))
        return super().unlink()


class ResBank(models.Model):
    _inherit = "res.bank"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete bank."))
        return super().unlink()


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete partner bank."))
        return super().unlink()
