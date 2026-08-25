"""Sale order line extensions for transport tariff calculation."""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

class SaleOrderLine(models.Model):
    """Compute transport line prices from configured waste transport tariffs."""
    _inherit = 'sale.order.line'

    # ---------------------------------------------------------
    # TRANSPORT TARIFF HELPER
    # ---------------------------------------------------------
    def _get_transport_tariff(self, rate_type):
        """Resolve the active transport tariff for a given rate type."""

        Tariff = self.env['waste.transport.tariff'].sudo()

        today = fields.Date.context_today(self)

        # Company tariff first
        tariff = Tariff.search([
            ('company_id', '=', self.company_id.id),
            ('rate_type', '=', rate_type),
            ('active', '=', True),
            ('date_from', '<=', today),
            '|',
            ('date_to', '=', False),
            ('date_to', '>=', today),
        ], limit=1)

        # Global tariff fallback
        if not tariff:
            tariff = Tariff.search([
                ('company_id', '=', False),
                ('rate_type', '=', rate_type),
                ('active', '=', True),
                ('date_from', '<=', today),
                '|',
                ('date_to', '=', False),
                ('date_to', '>=', today),
            ], limit=1)

        if not tariff:
            raise ValidationError(_(
                "No active transport tariff found for:\n"
                "- Rate Type: %s",
                rate_type
            ))

        return tariff

    # ---------------------------------------------------------
    # TRANSPORT OPERATIONAL FIELDS
    # ---------------------------------------------------------
    number_of_bins = fields.Integer(
        string="Number of Bins",
        default=0,
        tracking=True,
    )

    distance_km = fields.Float(
        string="Distance (KM)",
        tracking=True,
    )

    number_of_trips = fields.Integer(
        string="Trips",
        default=0,
        tracking=True,
    )

    weight_kg = fields.Float(
        string="Weight (KG)",
    )

    weight_ton = fields.Float(
        string="Weight (Ton)",
    )

    product_transport_rate_type = fields.Selection(
        related='product_id.product_tmpl_id.transport_rate_type',
        string='Transport Rate Type',
        store=False,
    )

    # ---------------------------------------------------------
    # TRANSPORT CALCULATION
    # ---------------------------------------------------------
    @api.onchange(
        'number_of_bins',
        'distance_km',
        'number_of_trips',
        'weight_ton',
        'weight_kg',
        'product_id'
    )
    def _compute_transport_amount(self):
        """Recalculate line price from transport tariff rules."""

        for line in self:

            if not line.product_id:
                continue

            product = line.product_id.product_tmpl_id

            # -------------------------------------------------
            # ONLY TRANSPORT PRODUCTS
            # -------------------------------------------------
            if not product.is_transport_service:
                continue

            rate_type = product.transport_rate_type

            bins = line.number_of_bins or 1
            km = line.distance_km or 0
            trips = line.number_of_trips or 1

            amount = 0.0

            # =================================================
            # FLAT RATE
            # Formula:
            # base + ((bins - 1) * increment)
            # =================================================
            if rate_type == 'flat':

                tariff = line._get_transport_tariff(
                    'flat'
                )

                amount = (
                    tariff.base_rate +
                    ((bins - 1) * tariff.increment_rate)
                )

            # =================================================
            # PER BIN
            # Formula:
            # bins * rate
            # =================================================
            elif rate_type == 'per_bin':

                tariff = line._get_transport_tariff(
                    'per_bin'
                )

                amount = (
                    bins * tariff.per_bin_rate
                )

            # =================================================
            # PER TRIP
            # Formula:
            # trips * rate
            # =================================================
            elif rate_type == 'per_trip':

                tariff = line._get_transport_tariff(
                    'per_trip'
                )

                amount = (
                    trips * tariff.per_trip_rate
                )

            # =================================================
            # PER TON
            # Formula:
            # TON * rate
            # 5 tons × R850
            # = R4, 250
            # =================================================

            elif rate_type == 'per_ton':

                tariff = line._get_transport_tariff(
                    'per_ton'
                )

                amount = (
                        line.weight_ton *
                        tariff.per_ton_rate
                )

            # =================================================
            # PER KG
            # Formula:
            # KG * rate
            # 2500kg × R1.50
            # = R3, 750
            # =================================================

            elif rate_type == 'per_kg':

                tariff = line._get_transport_tariff(
                    'per_kg'
                )

                amount = (
                        line.weight_kg *
                        tariff.per_kg_rate
                )

            # =================================================
            # PER BIN PER KM
            # Formula:
            # bins * km * rate
            # =================================================
            # elif rate_type == 'per_bin_km':
            #
            #     tariff = line._get_transport_tariff(
            #         'per_bin_km'
            #     )
            #
            #     amount = (
            #         bins *
            #         km *
            #         tariff.per_km_rate
            #     )
            # elif rate_type == 'per_bin_km':
            #
            #     tariff = line._get_transport_tariff(
            #         'per_bin_km'
            #     )
            #
            #     amount = (
            #             (bins * tariff.per_bin_rate)
            #             +
            #             (bins * km * tariff.per_km_rate)
            #     )

            elif rate_type == 'per_bin_km':

                km_tariff = line._get_transport_tariff(
                    'per_bin_km'
                )

                per_bin_tariff = line._get_transport_tariff(
                    'per_bin'
                )

                amount = (
                        (bins * per_bin_tariff.per_bin_rate)
                        +
                        (bins * km * km_tariff.per_km_rate)
                )

            # =================================================
            # PER TRIP PER KM
            # Formula:
            # trips * km * rate
            # =================================================
            # elif rate_type == 'per_trip_km':
            #
            #     tariff = line._get_transport_tariff(
            #         'per_trip_km'
            #     )
            #
            #     amount = (
            #         trips *
            #         km *
            #         tariff.per_km_rate
            #     )

            elif rate_type == 'per_trip_km':

                km_tariff = line._get_transport_tariff(

                    'per_trip_km'

                )

                per_trip_tariff = line._get_transport_tariff(

                    'per_trip'

                )

                amount = (

                        (trips * per_trip_tariff.per_trip_rate)

                        +

                        (trips * km * km_tariff.per_km_rate)

                )

            # =================================================
            # TIERED BY BIN COUNT
            # =================================================
            elif rate_type == 'tier_bin':

                tariff = self.env[
                    'waste.transport.tariff'
                ].search([

                    ('company_id', '=', line.company_id.id),

                    ('rate_type', '=', 'tier_bin'),

                    ('min_bin_qty', '<=', bins),

                    '|',
                    ('max_bin_qty', '=', False),
                    ('max_bin_qty', '>=', bins),

                    ('active', '=', True),

                ], limit=1)

                if tariff:
                    amount = tariff.base_rate

            # =================================================
            # TIERED BY DISTANCE
            # =================================================
            elif rate_type == 'tier_distance':

                tariff = self.env[
                    'waste.transport.tariff'
                ].search([

                    ('company_id', '=', line.company_id.id),

                    ('rate_type', '=', 'tier_distance'),

                    ('min_distance', '<=', km),

                    '|',
                    ('max_distance', '=', False),
                    ('max_distance', '>=', km),

                    ('active', '=', True),

                ], limit=1)

                if tariff:
                    amount = tariff.base_rate

            # =================================================
            # HYBRID - BIN + TRIP
            # Formula:
            # base + (bins * rate)
            # =================================================
            elif rate_type == 'hybrid_bin_trip':

                tariff = line._get_transport_tariff(
                    'hybrid_bin_trip'
                )

                amount = (
                    tariff.base_rate +
                    (bins * tariff.per_bin_rate)
                )

            # =================================================
            # HYBRID - TRIP + KM
            # Formula:
            # (trips * base)
            # + (trips * km * rate)
            # =================================================
            elif rate_type == 'hybrid_trip_km':

                tariff = line._get_transport_tariff(
                    'hybrid_trip_km'
                )

                amount = (
                    tariff.base_rate
                    +
                    (
                        trips *
                        km *
                        tariff.per_km_rate
                    )
                )

            # =================================================
            # UPDATE SO LINE PRICE
            # =================================================
            line.price_unit = amount

    def _prepare_invoice_line(self, **optional_values):
        """Copy transport operational fields onto the invoice line."""

        res = super()._prepare_invoice_line(
            **optional_values
        )

        res.update({

            'number_of_bins': self.number_of_bins,

            'distance_km': self.distance_km,

            'number_of_trips': self.number_of_trips,

            'weight_kg': self.weight_kg,

            'weight_ton': self.weight_ton,

        })

        return res

    import logging
    _logger = logging.getLogger(__name__)

    def write(self, vals):
        """Log changes to number_of_bins for debugging transport sync."""

        if 'number_of_bins' in vals:
            _logger.warning(
                "NUMBER OF BINS CHANGED -> Line=%s Old=%s New=%s",
                self.ids,
                self.mapped('number_of_bins'),
                vals.get('number_of_bins')
            )

        return super().write(vals)
