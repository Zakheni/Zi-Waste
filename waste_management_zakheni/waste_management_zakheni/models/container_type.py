

"""Container type master data (bin vs tank) for service configuration."""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ContainerType(models.Model):
    """High-level container category linked to product attributes."""
    _name = "container.type"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Container Type"

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
        domain="[('attribute_id.name', '=', 'Container Type')]"
    )
    attribute_id = fields.Many2one('product.attribute', related="pav_id.attribute_id", store=False)
    _sql_constraints = [('uniq_pav', 'unique(pav_id)', 'This attribute value is already linked.')]

    @api.onchange('pav_id')
    def _onchange(self):
        """Sync container type name from the linked attribute value."""
        self.name = self.pav_id.name

    @api.constrains('name', 'pav_id')
    def _check(self):
        """Ensure name matches the selected attribute value."""
        for r in self:
            if r.pav_id and r.name.strip() != r.pav_id.name.strip():
                raise ValidationError(_("Name must match the selected attribute value."))

    @api.constrains('name')
    def _check_unique_name(self):
        """Ensure container type names are unique."""
        for rec in self:
            if rec.name:
                exists = self.search_count([
                    ('id', '!=', rec.id),
                    ('name', '=', rec.name),
                ])
                if exists:
                    raise ValidationError(
                        _("A Tank Volume with this name already exists.")
                    )
