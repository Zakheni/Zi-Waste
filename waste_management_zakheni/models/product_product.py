# models/product_template.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    waste_qty = fields.Float(
        string="Waste Request Qty",
        compute="_compute_waste_request_info",
        store=False,
    )
    waste_selected = fields.Boolean(
        string="Selected on Waste Request",
        compute="_compute_waste_request_info",
        store=False,
    )

    @api.depends_context('waste_request_id')
    def _compute_waste_request_info(self):
        """Compute qty + selected flag per product TEMPLATE for the active waste request."""
        request_id = self.env.context.get('waste_request_id')
        ExtraLine = self.env['waste.service.request.extra.line']

        # No request in context → nothing selected
        if not request_id:
            for tmpl in self:
                tmpl.waste_qty = 0.0
                tmpl.waste_selected = False
            return

        # Get all extra lines for this request and aggregate by product_tmpl_id
        lines = ExtraLine.search([
            ('request_id', '=', request_id),
            ('product_id', '!=', False),
        ])

        qty_by_tmpl = {}
        for l in lines:
            tmpl = l.product_id.product_tmpl_id
            if not tmpl:
                continue
            qty_by_tmpl[tmpl.id] = qty_by_tmpl.get(tmpl.id, 0.0) + (l.quantity or 0.0)

        for tmpl in self:
            qty = qty_by_tmpl.get(tmpl.id, 0.0)
            tmpl.waste_qty = qty
            tmpl.waste_selected = qty > 0

    # ==== helper used by buttons ====
    def _update_waste_request_line(self, delta_qty):
        request_id = self.env.context.get('waste_request_id')
        if not request_id:
            # If opened from generic product menu, just ignore the click
            return False

        request = self.env['waste.service.request'].browse(request_id)
        request.ensure_one()

        ExtraLine = self.env['waste.service.request.extra.line']
        for tmpl in self:
            product = tmpl.product_variant_id
            if not product:
                continue

            line = ExtraLine.search([
                ('request_id', '=', request.id),
                ('product_id', '=', product.id),
            ], limit=1)

            if line:
                new_qty = (line.quantity or 0.0) + delta_qty
                if new_qty <= 0:
                    line.unlink()
                else:
                    line.quantity = new_qty
            elif delta_qty > 0:
                ExtraLine.create({
                    'request_id': request.id,
                    'product_id': product.id,
                    'quantity': delta_qty,
                    'price_unit': product.lst_price,
                })
        return False


    def action_waste_add_one(self):
        return self._update_waste_request_line(1)

    def action_waste_remove_one(self):
        return self._update_waste_request_line(-1)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def remove_sale_order_line_safe(self):
        """
        Safely remove a sale order line:
        - If order is confirmed (sale / done) → set quantity to 0
        - If order is draft / sent → delete the line
        """
        for line in self:
            if line.order_id.state in ('sale', 'done'):
                line.write({'product_uom_qty': 0})
            else:
                super(SaleOrderLine, line).unlink()
