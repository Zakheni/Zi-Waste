from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ---------------------------------------------------------
    # TRANSPORT TARIFF HELPER
    # ---------------------------------------------------------
    def _get_transport_tariff(self, tariff_code):

        Tariff = self.env['waste.transport.tariff'].sudo()

        today = fields.Date.context_today(self)

        tariff = Tariff.search([
            ('company_id', '=', self.company_id.id),
            ('code', '=', tariff_code),
            ('active', '=', True),
            ('date_from', '<=', today),
            '|',
            ('date_to', '=', False),
            ('date_to', '>=', today),
        ], limit=1)

        if not tariff:
            raise ValidationError(_(
                "No active transport tariff found for:\n"
                "- Tariff Type: %s",
                tariff_code
            ))

        return tariff

    # ---------------------------------------------------------
    # TRANSPORT OPERATIONAL FIELDS
    # ---------------------------------------------------------
    number_of_bins = fields.Integer(
        string="Number of Bins",
        default=1,
        tracking=True,
    )

    distance_km = fields.Float(
        string="Distance (KM)",
        tracking=True,
    )

    number_of_trips = fields.Integer(
        string="Trips",
        default=1,
        tracking=True,
    )

    # @api.onchange(
    #     'number_of_bins',
    #     'distance_km',
    #     'number_of_trips',
    #     'product_id'
    # )
    # def _compute_transport_amount(self):
    #
    #     for line in self:
    #
    #         if not line.product_id:
    #             continue
    #
    #         product = line.product_id.product_tmpl_id
    #
    #         # -------------------------------------------------
    #         # ONLY TRANSPORT PRODUCTS
    #         # -------------------------------------------------
    #         if not product.is_transport_service:
    #             continue
    #
    #         rate_type = product.transport_rate_type
    #
    #         bins = line.number_of_bins or 0
    #         km = line.distance_km or 0
    #         trips = line.number_of_trips or 1
    #
    #         amount = 0.0
    #
    #         # -------------------------------------------------
    #         # FLAT RATE
    #         # -------------------------------------------------
    #         if rate_type == 'flat_single':
    #
    #             tariff = line._get_transport_tariff(
    #                 'flat_single'
    #             )
    #
    #             amount = tariff.single_bin_price
    #
    #         elif rate_type == 'flat_multiple':
    #
    #             tariff = line._get_transport_tariff(
    #                 'flat_multiple'
    #             )
    #
    #             amount = tariff.multiple_bin_price
    #
    #         # -------------------------------------------------
    #         # PER BIN
    #         # -------------------------------------------------
    #         elif rate_type in (
    #                 'per_bin_single',
    #                 'per_bin_multiple',
    #         ):
    #
    #             tariff = line._get_transport_tariff(
    #                 rate_type
    #             )
    #
    #             amount = bins * tariff.per_bin_rate
    #
    #         # -------------------------------------------------
    #         # PER TRIP
    #         # -------------------------------------------------
    #         elif rate_type == 'per_trip':
    #
    #             tariff = line._get_transport_tariff(
    #                 rate_type
    #             )
    #
    #             amount = trips * tariff.per_trip_rate
    #
    #         # -------------------------------------------------
    #         # PER BIN PER KM
    #         # -------------------------------------------------
    #         elif rate_type in (
    #                 'per_bin_per_km_single',
    #                 'per_bin_per_km_multiple',
    #         ):
    #
    #             tariff = line._get_transport_tariff(
    #                 rate_type
    #             )
    #
    #             amount = bins * km * tariff.per_km_rate
    #
    #         # -------------------------------------------------
    #         # PER TRIP PER KM
    #         # -------------------------------------------------
    #         elif rate_type == 'per_trip_per_km':
    #
    #             tariff = line._get_transport_tariff(
    #                 rate_type
    #             )
    #
    #             amount = trips * km * tariff.per_km_rate
    #
    #         # -------------------------------------------------
    #         # HYBRID BIN + TRIP
    #         # -------------------------------------------------
    #         elif rate_type == 'hybrid_bin_trip':
    #
    #             tariff = line._get_transport_tariff(
    #                 rate_type
    #             )
    #
    #             amount = (
    #                     tariff.base_rate +
    #                     (bins * tariff.per_bin_rate)
    #             )
    #
    #         # -------------------------------------------------
    #         # HYBRID TRIP + KM
    #         # -------------------------------------------------
    #         elif rate_type == 'hybrid_trip_km':
    #
    #             tariff = line._get_transport_tariff(
    #                 rate_type
    #             )
    #
    #             amount = (
    #                     tariff.base_rate +
    #                     (km * tariff.per_km_rate * trips)
    #             )
    #
    #         # -------------------------------------------------
    #         # UPDATE PRICE
    #         # -------------------------------------------------
    #         line.price_unit = amount
    #

    @api.onchange(
        'number_of_bins',
        'distance_km',
        'number_of_trips',
        'product_id'
    )
    def _compute_transport_amount(self):

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

            bins = line.number_of_bins or 0
            km = line.distance_km or 0
            trips = line.number_of_trips or 1

            amount = 0.0

            # -------------------------------------------------
            # FLAT RATE - SINGLE BIN
            # -------------------------------------------------
            if rate_type == 'flat_single':

                tariff = line._get_transport_tariff(
                    'flat_single'
                )

                if bins == 1:
                    amount = tariff.single_bin_price

            # -------------------------------------------------
            # FLAT RATE - MULTIPLE BINS
            # -------------------------------------------------
            elif rate_type == 'flat_multiple':

                tariff = line._get_transport_tariff(
                    'flat_multiple'
                )

                if bins > 1:
                    amount = tariff.multiple_bin_price

            # -------------------------------------------------
            # PER BIN
            # -------------------------------------------------
            elif rate_type in (
                    'per_bin_single',
                    'per_bin_multiple',
            ):

                tariff = line._get_transport_tariff(
                    rate_type
                )

                amount = bins * tariff.per_bin_rate

            # -------------------------------------------------
            # PER TRIP
            # -------------------------------------------------
            elif rate_type == 'per_trip':

                tariff = line._get_transport_tariff(
                    rate_type
                )

                amount = trips * tariff.per_trip_rate

            # -------------------------------------------------
            # PER BIN PER KM
            # -------------------------------------------------
            elif rate_type in (
                    'per_bin_per_km_single',
                    'per_bin_per_km_multiple',
            ):

                tariff = line._get_transport_tariff(
                    rate_type
                )

                amount = bins * km * tariff.per_km_rate

            # -------------------------------------------------
            # PER TRIP PER KM
            # -------------------------------------------------
            elif rate_type == 'per_trip_per_km':

                tariff = line._get_transport_tariff(
                    rate_type
                )

                amount = trips * km * tariff.per_km_rate

            # -------------------------------------------------
            # TIERED BIN COUNT - 1 BIN
            # -------------------------------------------------
            elif rate_type == 'tier_bin_1':

                tariff = line._get_transport_tariff(
                    rate_type
                )

                if bins == 1:
                    amount = tariff.rate

            # -------------------------------------------------
            # TIERED BIN COUNT - 2 TO 3
            # -------------------------------------------------
            elif rate_type == 'tier_bin_2_3':

                tariff = line._get_transport_tariff(
                    rate_type
                )

                if bins >= 2 and bins <= 3:
                    amount = tariff.rate

            # -------------------------------------------------
            # TIERED BIN COUNT - 4+
            # -------------------------------------------------
            elif rate_type == 'tier_bin_4_plus':

                tariff = line._get_transport_tariff(
                    rate_type
                )

                if bins >= 4:
                    amount = tariff.rate

            # -------------------------------------------------
            # TIERED DISTANCE - 0 TO 10 KM
            # -------------------------------------------------
            elif rate_type == 'tier_distance_0_10':

                tariff = line._get_transport_tariff(
                    rate_type
                )

                if km >= 0 and km <= 10:
                    amount = tariff.rate

            # -------------------------------------------------
            # TIERED DISTANCE - 11 TO 30 KM
            # -------------------------------------------------
            elif rate_type == 'tier_distance_11_30':

                tariff = line._get_transport_tariff(
                    rate_type
                )

                if km >= 11 and km <= 30:
                    amount = tariff.rate

            # -------------------------------------------------
            # TIERED DISTANCE - 31+ KM
            # -------------------------------------------------
            elif rate_type == 'tier_distance_31_plus':

                tariff = line._get_transport_tariff(
                    rate_type
                )

                if km >= 31:
                    amount = tariff.rate

            # -------------------------------------------------
            # HYBRID - PER BIN + FLAT TRIP
            # -------------------------------------------------
            elif rate_type == 'hybrid_bin_trip':

                tariff = line._get_transport_tariff(
                    rate_type
                )

                amount = (
                        tariff.base_rate +
                        (bins * tariff.per_bin_rate)
                )

            # -------------------------------------------------
            # HYBRID - TRIP + KM
            # -------------------------------------------------
            elif rate_type == 'hybrid_trip_km':

                tariff = line._get_transport_tariff(
                    rate_type
                )

                amount = (
                        tariff.base_rate +
                        (km * tariff.per_km_rate)
                )

            # -------------------------------------------------
            # UPDATE SO LINE PRICE
            # -------------------------------------------------
            line.price_unit = amount