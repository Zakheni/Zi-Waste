from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError


class WasteType(models.Model):
    _name = 'waste.type'
    _description = 'Waste Type'

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True)
    sequence = fields.Integer("Sequence", default=10)

    pav_id = fields.Many2one(
        'product.attribute.value',
        domain="[('attribute_id.name', '=', 'Waste Type')]"
    )
    attribute_id = fields.Many2one('product.attribute', related="pav_id.attribute_id", store=False)
    _sql_constraints = [('uniq_pav', 'unique(pav_id)', 'This attribute value is already linked.')]

    @api.onchange('pav_id')
    def _onchange(self):
        self.name = self.pav_id.name

    @api.constrains('name', 'pav_id')
    def _check(self):
        for r in self:
            if r.pav_id and r.name.strip() != r.pav_id.name.strip():
                raise ValidationError(_("Name must match the selected attribute value."))