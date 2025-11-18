# models/product_product.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ProductProduct(models.Model):
    _inherit = 'product.product'

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
        """Compute qty + selected flag per product for the active waste request."""
        request_id = self.env.context.get('waste_request_id')
        ExtraLine = self.env['waste.service.request.extra.line']

        # No request in context → nothing selected
        if not request_id:
            for prod in self:
                prod.waste_qty = 0.0
                prod.waste_selected = False
            return

        # Group lines per product for this request
        lines = ExtraLine.read_group(
            [('request_id', '=', request_id), ('product_id', 'in', self.ids)],
            ['product_id', 'quantity:sum'],
            ['product_id'],
        )
        qty_map = {l['product_id'][0]: l['quantity'] for l in lines}

        for prod in self:
            qty = qty_map.get(prod.id, 0.0)
            prod.waste_qty = qty
            prod.waste_selected = qty > 0

    # ==== existing helper used by buttons ====
    def _update_waste_request_line(self, delta_qty):
        request_id = self.env.context.get('waste_request_id')
        if not request_id:
            raise UserError(_("No waste request in context."))

        request = self.env['waste.service.request'].browse(request_id)
        request.ensure_one()

        ExtraLine = self.env['waste.service.request.extra.line']
        for product in self:
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



#
# # models/product_product.py
# from odoo import models, api, _
# from odoo.exceptions import UserError
#
# class ProductProduct(models.Model):
#     _inherit = 'product.product'
#
#     def _update_waste_request_line(self, delta_qty):
#         """delta_qty: +1, -1, etc. Updates extra products on waste.service.request."""
#         request_id = self.env.context.get('waste_request_id')
#         if not request_id:
#             # called outside a waste request
#             raise UserError(_("No waste request in context."))
#
#         request = self.env['waste.service.request'].browse(request_id)
#         request.ensure_one()
#
#         ExtraLine = self.env['waste.service.request.extra.line']
#         for product in self:
#             line = ExtraLine.search([
#                 ('request_id', '=', request.id),
#                 ('product_id', '=', product.id),
#             ], limit=1)
#
#             if line:
#                 new_qty = (line.quantity or 0.0) + delta_qty
#                 if new_qty <= 0:
#                     line.unlink()
#                 else:
#                     line.quantity = new_qty
#             elif delta_qty > 0:
#                 ExtraLine.create({
#                     'request_id': request.id,
#                     'product_id': product.id,
#                     'quantity': delta_qty,
#                     'price_unit': product.lst_price,
#                 })
#
#         # return False so Odoo just stays on the kanban
#         return False
#
#     def action_waste_add_one(self):
#         return self._update_waste_request_line(1)
#
#     def action_waste_remove_one(self):
#         return self._update_waste_request_line(-1)
#
#
# # # models/product_product.py
# # from odoo import models, api, _
# # from odoo.exceptions import UserError
# #
# # class ProductProduct(models.Model):
# #     _inherit = 'product.product'
# #
# #     def _update_waste_request_line(self, delta_qty):
# #         """delta_qty: +1, -1, etc."""
# #         request_id = self.env.context.get('waste_request_id')
# #         if not request_id:
# #             raise UserError(_("No waste request in context."))
# #
# #         request = self.env['waste.service.request'].browse(request_id).sudo()
# #         request.ensure_one()
# #
# #         ExtraLine = self.env['waste.service.request.extra.line']
# #         for product in self:
# #             line = ExtraLine.search([
# #                 ('request_id', '=', request.id),
# #                 ('product_id', '=', product.id),
# #             ], limit=1)
# #             if line:
# #                 new_qty = (line.quantity or 0.0) + delta_qty
# #                 if new_qty <= 0:
# #                     line.unlink()
# #                 else:
# #                     line.quantity = new_qty
# #             elif delta_qty > 0:
# #                 ExtraLine.create({
# #                     'request_id': request.id,
# #                     'product_id': product.id,
# #                     'quantity': delta_qty,
# #                     'price_unit': product.lst_price,
# #                 })
# #         # stay on the grid
# #         return False
# #
# #     def action_waste_add_one(self):
# #         return self._update_waste_request_line(1)
# #
# #     def action_waste_remove_one(self):
# #         return self._update_waste_request_line(-1)
