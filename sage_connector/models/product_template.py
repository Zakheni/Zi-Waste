"""Sage item code alias on product templates."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    """Expose sage_code as a stable alias of x_pastel_item_code."""

    _inherit = "product.template"

    sage_code = fields.Char(string="Sage Item Code", index=True, copy=False)

    def init(self):
        cr = self.env.cr
        cr.execute("""
            SELECT COUNT(*) FROM (
                SELECT COALESCE(company_id, 0), sage_code
                FROM product_template
                WHERE sage_code IS NOT NULL AND sage_code <> ''
                GROUP BY 1, 2 HAVING COUNT(*) > 1
            ) dup
        """)
        if cr.fetchone()[0]:
            return
        cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS product_template_sage_code_uniq
            ON product_template (COALESCE(company_id, 0), sage_code)
            WHERE sage_code IS NOT NULL AND sage_code <> ''
        """)

    @api.constrains("sage_code", "company_id")
    def _check_sage_code_unique(self):
        for rec in self:
            code = (rec.sage_code or "").strip()
            if not code:
                continue
            domain = [
                ("sage_code", "=", code),
                ("id", "!=", rec.id),
                ("company_id", "in", [rec.company_id.id, False] if rec.company_id else [False]),
            ]
            if rec.search_count(domain):
                raise ValidationError(_("Sage item code %s is already used.") % code)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("x_pastel_item_code") and not vals.get("sage_code"):
                vals["sage_code"] = vals["x_pastel_item_code"]
            if vals.get("sage_code") and not vals.get("x_pastel_item_code"):
                vals["x_pastel_item_code"] = vals["sage_code"]
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("x_pastel_item_code") and "sage_code" not in vals:
            vals = dict(vals, sage_code=vals["x_pastel_item_code"])
        if vals.get("sage_code") and "x_pastel_item_code" not in vals:
            vals = dict(vals, x_pastel_item_code=vals["sage_code"])
        return super().write(vals)
