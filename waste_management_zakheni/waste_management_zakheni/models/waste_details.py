"""Detailed waste description master data for tank tariff selection."""
from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError


class WasteDetails(models.Model):
    """Fine-grained waste detail (e.g. septic vs grease) for pricing."""
    _name = 'waste.details'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Waste Details'

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        default=lambda self: self.env.company,
        required=False,  # ✅ allow global/shared records
    )

    sequence = fields.Integer("Sequence", default=10)

    pav_id = fields.Many2one(
        'product.attribute.value',
        domain="[('attribute_id.name', '=', 'Waste Type')]"
    )
    attribute_id = fields.Many2one('product.attribute', related="pav_id.attribute_id", store=False)
    _sql_constraints = [('uniq_pav', 'unique(pav_id)', 'This attribute value is already linked.')]

    @api.onchange('pav_id')
    def _onchange(self):
        """Sync waste detail name from the linked attribute value."""
        self.name = self.pav_id.name

    @api.constrains('name', 'pav_id')
    def _check(self):
        """Ensure name matches the selected attribute value."""
        for r in self:
            if r.pav_id and r.name.strip() != r.pav_id.name.strip():
                raise ValidationError(_("Name must match the selected attribute value."))

    @api.constrains('name')
    def _check_unique_name(self):
        """Ensure waste detail names are unique."""
        for rec in self:
            if rec.name:
                exists = self.search_count([
                    ('id', '!=', rec.id),
                    ('name', '=', rec.name),
                ])
                if exists:
                    raise ValidationError(
                        _("A Waste Detail with this name already exists.")
                    )