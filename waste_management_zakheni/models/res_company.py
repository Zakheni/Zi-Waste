from odoo import models, fields, api, _
from odoo.exceptions import (ValidationError)
import re

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    # @api.model_create_multi
    # def create(self, vals_list):
    #     companies = super().create(vals_list)
    #     for company in companies:
    #         if not company.create_uid:
    #             company.create_uid = self.env.user.id
    #     return companies

    # Services (service_requested_id on waste.service.request)


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

    # mobile = fields.Char(required=True)

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
        companies = super().create(vals_list)

        for company in companies:
            partner = company.partner_id
            if not partner:
                continue

            vals = {}
            if partner.phone:
                vals['phone'] = self._normalize_phone(partner.phone)
            if partner.mobile:
                vals['mobile'] = self._normalize_phone(partner.mobile)

            if vals:
                partner.sudo().with_company(company).write(vals)

        return companies

    # ------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------
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
