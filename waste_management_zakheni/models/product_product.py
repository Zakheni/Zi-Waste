from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=False,
        default=lambda self: self.env.company,
        index=True
    )

    # ---------------------------------------------------------
    # TRANSPORT SERVICE
    # ---------------------------------------------------------
    is_transport_service = fields.Boolean(
        string="Transport Service"
    )

    # ---------------------------------------------------------
    # TRANSPORT RATE TYPE
    # ---------------------------------------------------------
    transport_rate_type = fields.Selection([

        ('flat', 'Flat Rate'),

        ('per_bin', 'Per Bin'),

        ('per_trip', 'Per Trip'),

        ('per_ton', 'Per Ton'),

        ('per_kg', 'Per KG'),

        ('per_bin_km', 'Per Bin Per KM'),

        ('per_trip_km', 'Per Trip Per KM'),

        ('tier_bin', 'Tiered By Bin Count'),

        ('tier_distance', 'Tiered By Distance'),

        ('hybrid_bin_trip', 'Hybrid - Per Bin + Flat Trip'),

        ('hybrid_trip_km', 'Hybrid - Trip + KM'),

    ],
        string="Transport Rate Type",
        tracking=True,
    )

    # ---------------------------------------------------------
    # AUTO POPULATE PRODUCT PRICE
    # ---------------------------------------------------------
    @api.onchange('transport_rate_type')
    def _onchange_transport_rate_type(self):

        for rec in self:

            if not rec.transport_rate_type:
                continue

            # tariff = self.env[
            #     'waste.transport.tariff'
            # ].search([
            #
            #     ('rate_type', '=', rec.transport_rate_type),
            #
            #     ('company_id', '=', rec.company_id.id),
            #
            #     ('active', '=', True),
            #
            # ], limit=1)

            # Company tariff first
            tariff = self.env[
                'waste.transport.tariff'
            ].search([

                ('rate_type', '=', rec.transport_rate_type),

                ('company_id', '=', rec.company_id.id),

                ('active', '=', True),

            ], limit=1)

            # Global tariff fallback
            if not tariff:
                tariff = self.env[
                    'waste.transport.tariff'
                ].search([

                    ('rate_type', '=', rec.transport_rate_type),

                    ('company_id', '=', False),

                    ('active', '=', True),

                ], limit=1)

            if not tariff:
                raise ValidationError(_(
                    "No active transport tariff found for:\n"
                    "- %s",
                    rec.transport_rate_type
                ))

            # -------------------------------------------------
            # RESET DEFAULT
            # -------------------------------------------------
            rec.list_price = 0.0

            # =================================================
            # FLAT RATE
            # =================================================
            if rec.transport_rate_type == 'flat':

                rec.list_price = tariff.base_rate

            # =================================================
            # PER BIN
            # =================================================
            elif rec.transport_rate_type == 'per_bin':

                rec.list_price = tariff.per_bin_rate

            # =================================================
            # PER TRIP
            # =================================================
            elif rec.transport_rate_type == 'per_trip':

                rec.list_price = tariff.per_trip_rate

            # =================================================
            # PER TON
            # =================================================
            elif rec.transport_rate_type == 'per_ton':

                rec.list_price = tariff.per_ton_rate

            # =================================================
            # PER KG
            # =================================================
            elif rec.transport_rate_type == 'per_kg':

                rec.list_price = tariff.per_kg_rate

            # =================================================
            # PER BIN PER KM
            # =================================================
            elif rec.transport_rate_type == 'per_bin_km':

                rec.list_price = tariff.per_km_rate

            # =================================================
            # PER TRIP PER KM
            # =================================================
            elif rec.transport_rate_type == 'per_trip_km':

                rec.list_price = tariff.per_km_rate

            # =================================================
            # TIERED BIN
            # =================================================
            elif rec.transport_rate_type == 'tier_bin':

                rec.list_price = tariff.rate

            # =================================================
            # TIERED DISTANCE
            # =================================================
            elif rec.transport_rate_type == 'tier_distance':

                rec.list_price = tariff.rate

            # =================================================
            # HYBRID BIN + TRIP
            # =================================================
            elif rec.transport_rate_type == 'hybrid_bin_trip':

                rec.list_price = tariff.base_rate

            # =================================================
            # HYBRID TRIP + KM
            # =================================================
            elif rec.transport_rate_type == 'hybrid_trip_km':

                rec.list_price = tariff.base_rate

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

# # models/product_template.py
# from odoo import models, fields, api, _
# from odoo.exceptions import UserError, ValidationError
#
#
# class ProductTemplate(models.Model):
#     _inherit = 'product.template'
#
#     company_id = fields.Many2one(
#         'res.company',
#         string='Company',
#         required=False,
#         default=lambda self: self.env.company,
#         index=True
#     )
#
#     # ---------------------------------------------------------
#     # # TRANSPORT SERVICE
#     # # ---------------------------------------------------------
#     # is_transport_service = fields.Boolean(
#     #     string="Transport Service"
#     # )
#     #
#     # # ---------------------------------------------------------
#     # # TRANSPORT RATE TYPE
#     # # ---------------------------------------------------------
#     # transport_rate_type = fields.Selection([
#     #
#     #     ('flat_single', 'Flat Rate - Single Bin'),
#     #     ('flat_multiple', 'Flat Rate - Multiple Bins'),
#     #
#     #     ('per_bin_single', 'Per Bin - Single Bin'),
#     #     ('per_bin_multiple', 'Per Bin - Multiple Bins'),
#     #
#     #     ('per_trip', 'Per Trip'),
#     #
#     #     ('per_bin_per_km_single', 'Per Bin Per KM - Single Bin'),
#     #     ('per_bin_per_km_multiple', 'Per Bin Per KM - Multiple Bins'),
#     #
#     #     ('per_trip_per_km', 'Per Trip Per KM'),
#     #
#     #     ('tier_bin_1', 'Tiered By Bin Count - 1 Bin'),
#     #     ('tier_bin_2_3', 'Tiered By Bin Count - 2 To 3 Bins'),
#     #     ('tier_bin_4_plus', 'Tiered By Bin Count - 4+ Bins'),
#     #
#     #     ('tier_distance_0_10', 'Tiered By Distance - 0 To 10 KM'),
#     #     ('tier_distance_11_30', 'Tiered By Distance - 11 To 30 KM'),
#     #     ('tier_distance_31_plus', 'Tiered By Distance - 31+ KM'),
#     #
#     #     ('hybrid_bin_trip', 'Hybrid - Per Bin + Flat Trip'),
#     #     ('hybrid_trip_km', 'Hybrid - Trip + KM'),
#     #
#     # ],
#     #     string="Transport Rate Type",
#     # )
#     #
#     # @api.onchange('transport_rate_type')
#     # def _onchange_transport_rate_type(self):
#     #
#     #     for rec in self:
#     #
#     #         if not rec.transport_rate_type:
#     #             continue
#     #
#     #         tariff = self.env[
#     #             'waste.transport.tariff'
#     #         ].search([
#     #             ('code', '=', rec.transport_rate_type),
#     #             ('company_id', '=', rec.company_id.id),
#     #             ('active', '=', True),
#     #         ], limit=1)
#     #
#     #         if not tariff:
#     #             raise ValidationError(_(
#     #                 "No active transport tariff found for:\n"
#     #                 "- %s",
#     #                 rec.transport_rate_type
#     #             ))
#     #
#     #         # Reset default
#     #         rec.list_price = 0.0
#     #
#     #         # -------------------------------------------------
#     #         # FLAT RATE - SINGLE BIN
#     #         # -------------------------------------------------
#     #         if rec.transport_rate_type == 'flat_single':
#     #
#     #             rec.list_price = tariff.single_bin_price
#     #
#     #         # -------------------------------------------------
#     #         # FLAT RATE - MULTIPLE BINS
#     #         # -------------------------------------------------
#     #         elif rec.transport_rate_type == 'flat_multiple':
#     #
#     #             rec.list_price = tariff.multiple_bin_price
#     #
#     #         # -------------------------------------------------
#     #         # PER BIN
#     #         # -------------------------------------------------
#     #         elif rec.transport_rate_type in (
#     #                 'per_bin_single',
#     #                 'per_bin_multiple',
#     #         ):
#     #
#     #             rec.list_price = tariff.per_bin_rate
#     #
#     #         # -------------------------------------------------
#     #         # PER TRIP
#     #         # -------------------------------------------------
#     #         elif rec.transport_rate_type == 'per_trip':
#     #
#     #             rec.list_price = tariff.per_trip_rate
#     #
#     #         # -------------------------------------------------
#     #         # PER BIN PER KM
#     #         # Base KM rate
#     #         # -------------------------------------------------
#     #         elif rec.transport_rate_type in (
#     #                 'per_bin_per_km_single',
#     #                 'per_bin_per_km_multiple',
#     #         ):
#     #
#     #             rec.list_price = tariff.per_km_rate
#     #
#     #         # -------------------------------------------------
#     #         # PER TRIP PER KM
#     #         # Base KM rate
#     #         # -------------------------------------------------
#     #         elif rec.transport_rate_type == 'per_trip_per_km':
#     #
#     #             rec.list_price = tariff.per_km_rate
#     #
#     #         # -------------------------------------------------
#     #         # TIERED BIN COUNT
#     #         # -------------------------------------------------
#     #         elif rec.transport_rate_type in (
#     #                 'tier_bin_1',
#     #                 'tier_bin_2_3',
#     #                 'tier_bin_4_plus',
#     #         ):
#     #
#     #             rec.list_price = tariff.rate
#     #
#     #         # -------------------------------------------------
#     #         # TIERED DISTANCE
#     #         # -------------------------------------------------
#     #         elif rec.transport_rate_type in (
#     #                 'tier_distance_0_10',
#     #                 'tier_distance_11_30',
#     #                 'tier_distance_31_plus',
#     #         ):
#     #
#     #             rec.list_price = tariff.rate
#     #
#     #         # -------------------------------------------------
#     #         # HYBRID - PER BIN + FLAT TRIP
#     #         # -------------------------------------------------
#     #         elif rec.transport_rate_type == 'hybrid_bin_trip':
#     #
#     #             rec.list_price = tariff.base_rate
#     #
#     #         # -------------------------------------------------
#     #         # HYBRID - TRIP + KM
#     #         # -------------------------------------------------
#     #         elif rec.transport_rate_type == 'hybrid_trip_km':
#     #
#     #             rec.list_price = tariff.base_rate
#
#     waste_qty = fields.Float(
#         string="Waste Request Qty",
#         compute="_compute_waste_request_info",
#         store=False,
#     )
#     waste_selected = fields.Boolean(
#         string="Selected on Waste Request",
#         compute="_compute_waste_request_info",
#         store=False,
#     )
#
#     @api.depends_context('waste_request_id')
#     def _compute_waste_request_info(self):
#         """Compute qty + selected flag per product TEMPLATE for the active waste request."""
#         request_id = self.env.context.get('waste_request_id')
#         ExtraLine = self.env['waste.service.request.extra.line']
#
#         # No request in context → nothing selected
#         if not request_id:
#             for tmpl in self:
#                 tmpl.waste_qty = 0.0
#                 tmpl.waste_selected = False
#             return
#
#         # Get all extra lines for this request and aggregate by product_tmpl_id
#         lines = ExtraLine.search([
#             ('request_id', '=', request_id),
#             ('product_id', '!=', False),
#         ])
#
#         qty_by_tmpl = {}
#         for l in lines:
#             tmpl = l.product_id.product_tmpl_id
#             if not tmpl:
#                 continue
#             qty_by_tmpl[tmpl.id] = qty_by_tmpl.get(tmpl.id, 0.0) + (l.quantity or 0.0)
#
#         for tmpl in self:
#             qty = qty_by_tmpl.get(tmpl.id, 0.0)
#             tmpl.waste_qty = qty
#             tmpl.waste_selected = qty > 0
#
#     # ==== helper used by buttons ====
#     def _update_waste_request_line(self, delta_qty):
#         request_id = self.env.context.get('waste_request_id')
#         if not request_id:
#             # If opened from generic product menu, just ignore the click
#             return False
#
#         request = self.env['waste.service.request'].browse(request_id)
#         request.ensure_one()
#
#         ExtraLine = self.env['waste.service.request.extra.line']
#         for tmpl in self:
#             product = tmpl.product_variant_id
#             if not product:
#                 continue
#
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
#         return False
#
#
#     def action_waste_add_one(self):
#         return self._update_waste_request_line(1)
#
#     def action_waste_remove_one(self):
#         return self._update_waste_request_line(-1)
#
#
# class SaleOrderLine(models.Model):
#     _inherit = 'sale.order.line'
#
#     def remove_sale_order_line_safe(self):
#         """
#         Safely remove a sale order line:
#         - If order is confirmed (sale / done) → set quantity to 0
#         - If order is draft / sent → delete the line
#         """
#         for line in self:
#             if line.order_id.state in ('sale', 'done'):
#                 line.write({'product_uom_qty': 0})
#             else:
#                 super(SaleOrderLine, line).unlink()
