"""Company-level waste configuration (allowed services, types, tariffs)."""
from odoo import models, fields, api, _
from odoo.exceptions import (ValidationError)
import re

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'

from odoo import models, fields


class ResCompany(models.Model):
    """Scope master data and defaults per operating company."""
    _inherit = "res.company"

    wmz_service_ids = fields.Many2many(
        "service.request",
        "wmz_company_service_rel",
        "company_id",
        "service_id",
        string="Waste Services for Company",
        help="Which service offerings this company uses on Waste Service Requests."
    )

    # Container types (container_type_id on waste.service.request)
    wmz_container_type_ids = fields.Many2many(
        "container.type",
        "wmz_company_container_type_rel",
        "company_id",
        "container_type_id",
        string="Container Types for Company",
        help="Which container types (Bins/Tanks) this company is configured for."
    )
    # Waste types (waste_type_id on waste.service.request)
    wmz_waste_type_ids = fields.Many2many(
        "waste.type",
        "wmz_company_waste_type_rel",
        "company_id",
        "waste_type_id",
        string="Waste Types for Company",
        help="Which waste types this company is configured for."
    )

    wmz_waste_details_ids = fields.Many2many(
        "waste.details",
        "wmz_company_waste_details_rel",
        "company_id",
        "waste_details_id",
        string="Waste Details for Company",
        help="Which waste details this company is configured for."
    )

    wmz_bin_type_ids = fields.Many2many(
        "bin.type",
        "wmz_company_bin_type_rel",
        "company_id",
        "bin_type_id",
        string="Allowed Bin Sizes",
    )

    wmz_tank_volume_ids = fields.Many2many(
        "tank.volume",
        "wmz_company_tank_volume_rel",
        "company_id",
        "tank_volume_id",
        string="Allowed Tank Volumes",
    )

    phone = fields.Char(required=True)
    email = fields.Char(required=True)
    is_branch = fields.Boolean(string="Is Branch", default=False, readonly=True)

    # ------------------------------------------------------------
    # Helper: normalize phone numbers
    # ------------------------------------------------------------
    def _normalize_phone(self, value):
        """
        +27 12 345 6789  → +27123456789
        (+27)12-345-6789 → +27123456789
        """
        if not value:
            return value
        return re.sub(r'[\s\-\(\)]+', '', value)

    # ------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user
        new_vals_list = []

        for vals in vals_list:
            if user.has_group('base.group_system'):
                new_vals_list.append(vals)
                continue

            if user.has_group('waste_management_zakheni.group_wmz_admin') or \
                    user.has_group('waste_management_zakheni.group_wmz_admin_clerk'):
                vals['parent_id'] = user.company_id.id
                vals['is_branch'] = True
                new_vals_list.append(vals)
                continue

            if user.has_group('waste_management_zakheni.group_central_admin'):
                vals.setdefault('is_branch', True)
                parent_id = vals.get('parent_id') or user.company_id.id
                if parent_id not in user.company_ids.ids:
                    raise ValidationError(_(
                        "You can only create branches under your allowed companies."
                    ))
                vals['parent_id'] = parent_id
                new_vals_list.append(vals)
                continue

            if user.has_group('waste_management_zakheni.group_company_admin'):
                vals['parent_id'] = user.company_id.id
                vals['is_branch'] = True
                new_vals_list.append(vals)
                continue

            raise ValidationError(_("You are not allowed to create a company."))

        # 🔥 Create companies
        companies = super().create(new_vals_list)

        # Link each company partner to its res.company record (POPIA isolation).
        for company in companies:
            partner = company.partner_id
            if partner and partner.company_id != company:
                partner.sudo().write({'company_id': company.id})

        # 🔥 FIX: remove chart template for branches
        for company in companies:
            if company.is_branch:
                company.chart_template = False

        # Assign customer reference on the auto-created company partner
        for company in companies:
            partner = company.partner_id
            if partner and partner._needs_customer_reference():
                partner.sudo().write({
                    'customer_reference': partner._next_customer_reference(),
                })

        # Normalize partner phone/mobile
        for company in companies:
            partner = company.partner_id
            if not partner:
                continue

            vals_partner = {}
            if partner.phone:
                vals_partner['phone'] = self._normalize_phone(partner.phone)
            if partner.mobile:
                vals_partner['mobile'] = self._normalize_phone(partner.mobile)

            if vals_partner:
                partner.sudo().with_company(company).write(vals_partner)

        self._wmz_apply_portal_quotation_policy(companies)

        return companies

    @api.model
    def _wmz_get_master_company(self):
        """Zakheni ICT — sign-only quotations (Accept & Sign, no online payment)."""
        master = self.sudo().search([("name", "ilike", "zakheni")], order="id", limit=1)
        return master or self.sudo().browse(1)

    @api.model
    def _wmz_apply_portal_quotation_policy(self, companies=None):
        """Zakheni: Accept & Sign. All other companies: Sign & Pay (100% prepayment)."""
        master = self._wmz_get_master_company()
        targets = companies if companies is not None else self.sudo().search([])
        for company in targets:
            if company.id == master.id:
                company.write({
                    "portal_confirmation_sign": True,
                    "portal_confirmation_pay": False,
                })
            else:
                company.write({
                    "portal_confirmation_sign": True,
                    "portal_confirmation_pay": True,
                    "prepayment_percent": 1.0,
                })
    # ------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------
    # def write(self, vals):
    #     res = super().write(vals)
    #
    #     for company in self:
    #         partner = company.partner_id
    #         if not partner:
    #             continue
    #
    #         vals_partner = {}
    #         if partner.phone:
    #             vals_partner['phone'] = self._normalize_phone(partner.phone)
    #         if partner.mobile:
    #             vals_partner['mobile'] = self._normalize_phone(partner.mobile)
    #
    #         if vals_partner:
    #             partner.sudo().with_company(company).write(vals_partner)
    #
    #     return res

    def write(self, vals):
        res = super().write(vals)

        for company in self:
            partner = company.partner_id
            if not partner:
                continue

            vals_partner = {}
            if partner.phone:
                vals_partner['phone'] = self._normalize_phone(partner.phone)
            if partner.mobile:
                vals_partner['mobile'] = self._normalize_phone(partner.mobile)

            if vals_partner:
                partner.sudo().with_company(company).write(vals_partner)

        return res
    # ------------------------------------------------------------
    # CONSTRAINT: validate company contact details
    # ------------------------------------------------------------
    @api.constrains('partner_id')
    def _check_company_contact_details(self):
        for company in self:
            partner = company.partner_id
            if not partner:
                continue

            # Email required
            if not partner.email:
                raise ValidationError(_("Company must have an email address."))

            if not re.match(EMAIL_REGEX, partner.email.strip()):
                raise ValidationError(
                    _("Invalid email address format: %s") % partner.email
                )

            # Phone required
            if not partner.phone:
                raise ValidationError(_("Company must have a phone number."))

            if not re.match(r'^\+\d{7,15}$', partner.phone):
                raise ValidationError(
                    _("Phone number must include country code, e.g. +27 12 345 6789")
                )

    @api.model
    def wmz_apply_green_theme(self):
        """Set Zakheni green as the global Odoo and website brand color."""
        from ..hooks import _apply_green_brand_theme
        _apply_green_brand_theme(self.env)
        return True
