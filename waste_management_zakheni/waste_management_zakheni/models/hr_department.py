"""HR department extensions for waste operations."""
from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError
import psycopg2

class HrDepartment(models.Model):
    """Department-level grouping for waste staff."""
    _inherit = 'hr.department'

    sequence_code = fields.Char(
        string='Department Code',
        readonly=True,
        copy=False
    )

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete Department."))
        return super().unlink()

    # 🔒 DATABASE CONSTRAINT (name + company)
    def init(self):
        super().init()
        self._cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            hr_department_unique_name_company
            ON hr_department (name, company_id)
            WHERE name IS NOT NULL
        """)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name'):
                # normalize name BEFORE uniqueness check
                vals['name'] = vals['name'].strip().title()

            if not vals.get('sequence_code'):
                vals['sequence_code'] = self.env['ir.sequence'].next_by_code(
                    'hr.department'
                ) or 'DEP/0000'

        try:
            return super().create(vals_list)
        except psycopg2.errors.UniqueViolation as e:
            self._cr.rollback()
            if 'hr_department_unique_name_company' in str(e):
                raise ValidationError(_(
                    'A department with this name already exists for this company.'
                ))
            raise

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = vals['name'].strip().title()

        try:
            return super().write(vals)
        except psycopg2.errors.UniqueViolation as e:
            self._cr.rollback()
            if 'hr_department_unique_name_company' in str(e):
                raise ValidationError(_(
                    'A department with this name already exists for this company.'
                ))
            raise
