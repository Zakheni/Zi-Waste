"""HR employee extensions for drivers and operational staff."""
import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'


class HREmployee(models.Model):
    """Link employees to fleet roles and waste notifications."""
    _inherit = 'hr.employee'

    _sql_constraints = [
        ('unique_user_employee',
         'unique(user_id)',
         'This user already has an employee profile!')
    ]

    service_request_id = fields.Many2one(
        'waste.service.request',
        string="Manifest",
        ondelete="set null"
    )
    planned_date = fields.Datetime(
        string="Planned Date",
        related="service_request_id.planned_date",
        store=True,
        readonly=True
    )

    work_email = fields.Char(required=True, tracking=True)
    work_phone = fields.Char(required=True, tracking=True)
    mobile_phone = fields.Char(tracking=True)
    job_id = fields.Many2one(required=True, tracking=True)
    deparment_id = fields.Many2one(required=True, tracking=True)
    parent_id = fields.Many2one(tracking=True)
    coach_id = fields.Many2one(tracking=True)





    # company_id = fields.Many2one(tracking=True)



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
    @api.model_create_multi
    def create(self, vals_list):
        """Apply waste module defaults for new employees."""
        for vals in vals_list:
            if vals.get('work_phone'):
                vals['work_phone'] = self._normalize_phone(vals['work_phone'])
            if vals.get('mobile_phone'):
                vals['mobile_phone'] = self._normalize_phone(vals['mobile_phone'])
        return super().create(vals_list)

    # ------------------------------------------------------------
    # WRITE: normalize BEFORE constraint
    # ------------------------------------------------------------
    def write(self, vals):
        if vals.get('work_phone'):
            vals['work_phone'] = self._normalize_phone(vals['work_phone'])
        if vals.get('mobile_phone'):
            vals['mobile_phone'] = self._normalize_phone(vals['mobile_phone'])
        return super().write(vals)

    # ------------------------------------------------------------
    # CONSTRAINT: validate normalized value ONLY
    # ------------------------------------------------------------
    @api.constrains('work_phone', 'mobile_phone')
    def _check_phone_country_code(self):
        for partner in self:
            for field in ('work_phone', 'mobile_phone'):
                value = partner[field]
                if not value:
                    continue

                if not re.match(r'^\+\d{7,15}$', value):
                    raise ValidationError(
                        _("Phone number must include country code, e.g. +27 12 345 6789, (+27)12-345-6789 and +27123456789 ✅ "
                          "\n and it must not include Alpha numeric ❌ ")
                    )

    @api.constrains('work_email')
    def _check_email_required(self):
        for partner in self:
            # Skip contacts that are not real business partners
            # if partner.is_company or partner.customer_rank > 0 or partner.supplier_rank > 0:
            if not partner.work_email:
                raise ValidationError(
                    _("Work Email address is required. ⚠️")
                )

    @api.constrains('work_email')
    def _check_email_format(self):
        for partner in self:
            if partner.work_email:
                work_email = partner.work_email.strip()
                if not re.match(EMAIL_REGEX, work_email):
                    raise ValidationError(
                        _("Invalid work email address format e.g email must take this format ✅'email@example.com' not this ❌: %s ") % work_email
                    )

    @api.model
    def _notification_recipient_domain(self, group_xmlid, job_name=None):
        """Build a reliable employee domain for users in a security group."""
        group = self.env.ref(group_xmlid, raise_if_not_found=False)
        if not group:
            return [('id', '=', False)]
        users = self.env['res.users'].search([
            ('groups_id', 'in', group.ids),
            ('active', '=', True),
            ('share', '=', False),
        ])
        company = self.env.company
        domain = [
            ('user_id', 'in', users.ids),
            ('work_email', '!=', False),
            '|', ('company_id', '=', False), ('company_id', '=', company.id),
        ]
        if job_name:
            domain.append(('job_id.name', '=', job_name))
        return domain

    @api.model
    def get_notification_email(self, employee):
        """Return the best email address for workflow notifications."""
        if not employee:
            return False
        for candidate in (
            employee.work_email,
            employee.user_id.email if employee.user_id else False,
            employee.user_id.partner_id.email if employee.user_id else False,
        ):
            email = (candidate or '').strip()
            if email:
                return email
        return False