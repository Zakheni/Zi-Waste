from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError


class ServiceRequest(models.Model):
    _name = 'service.request'
    _description = 'Service Request'

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True)
    sequence = fields.Integer("Sequence", default=10)

    pav_id = fields.Many2one(
        'product.attribute.value',
        string="Attribute Value",
        # required=True,
        domain="[('attribute_id.name', '=', 'Service Requested')]",
        help="Must point to a Product Attribute Value under the 'Service Requested' attribute."
    )
    attribute_id = fields.Many2one(
        'product.attribute',
        string="Attribute",
        related="pav_id.attribute_id",
        store=False,
        readonly=True,
    )

    _sql_constraints = [
        ('uniq_pav', 'unique(pav_id)', 'This attribute value is already linked.'),
    ]

    @api.onchange('pav_id')
    def _onchange_pav_id(self):
        if self.pav_id:
            self.name = self.pav_id.name

    @api.constrains('name', 'pav_id')
    def _check_name_matches_pav(self):
        for rec in self:
            if rec.pav_id and (rec.name or '').strip() != (rec.pav_id.name or '').strip():
                raise ValidationError(_("Name must match the selected attribute value (%s).") % rec.pav_id.name)