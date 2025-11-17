from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError


class WasteServiceRequestExtraLine(models.Model):
    _name = 'waste.service.request.extra.line'
    _description = 'Extra Product for Waste Service'

    request_id = fields.Many2one(
        'waste.service.request',
        string='Service Request',
        required=True,
        ondelete='cascade',
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
    )

    name = fields.Char(
        string='Description',
        related='product_id.display_name',
        readonly=True,
    )

    quantity = fields.Float(
        string='Quantity',
        default=1.0,
    )

    price_unit = fields.Float(
        string='Unit Price',
        default=0.0,
        help="Override product list price if needed."
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='request_id.company_id.currency_id',
        readonly=True,
        store=True,
    )

    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_price_subtotal',
        currency_field='currency_id',
    )

    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Sales Order Line',
        readonly=True,
        help="SO line created from this extra product.",
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id and not line.price_unit:
                line.price_unit = line.product_id.lst_price

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = (line.quantity or 0.0) * (line.price_unit or 0.0)
