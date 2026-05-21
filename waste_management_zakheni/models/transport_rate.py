from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class WasteTransportTariff(models.Model):
    _name = "waste.transport.tariff"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Transport Tariff Configuration"
    _rec_name = "name"
    _order = "company_id, code, date_from desc"

    # --------------------------------------------------
    # BASIC INFO
    # --------------------------------------------------
    name = fields.Char(
        string="Tariff Name",
        required=True,
        tracking=True,
    )

    code = fields.Selection([

        # --------------------------------------------------
        # FLAT RATES
        # --------------------------------------------------
        ('flat_single', 'Flat Rate - Single Bin'),
        ('flat_multiple', 'Flat Rate - Multiple Bins'),

        # --------------------------------------------------
        # PER BIN
        # --------------------------------------------------
        ('per_bin_single', 'Per Bin - Single Bin'),
        ('per_bin_multiple', 'Per Bin - Multiple Bins'),

        # --------------------------------------------------
        # PER TRIP
        # --------------------------------------------------
        ('per_trip', 'Per Trip'),

        # --------------------------------------------------
        # PER BIN PER KM
        # --------------------------------------------------
        ('per_bin_per_km_single', 'Per Bin Per KM - Single Bin'),
        ('per_bin_per_km_multiple', 'Per Bin Per KM - Multiple Bins'),

        # --------------------------------------------------
        # PER TRIP PER KM
        # --------------------------------------------------
        ('per_trip_per_km', 'Per Trip Per KM'),

        # --------------------------------------------------
        # TIERED BY BIN COUNT
        # --------------------------------------------------
        ('tier_bin_1', 'Tiered By Bin Count - 1 Bin'),
        ('tier_bin_2_3', 'Tiered By Bin Count - 2 to 3 Bins'),
        ('tier_bin_4_plus', 'Tiered By Bin Count - 4+ Bins'),

        # --------------------------------------------------
        # TIERED BY DISTANCE
        # --------------------------------------------------
        ('tier_distance_0_10', 'Tiered By Distance - 0 to 10 KM'),
        ('tier_distance_11_30', 'Tiered By Distance - 11 to 30 KM'),
        ('tier_distance_31_plus', 'Tiered By Distance - 31+ KM'),

        # --------------------------------------------------
        # HYBRID
        # --------------------------------------------------
        ('hybrid_bin_trip', 'Hybrid - Per Bin + Flat Trip'),
        ('hybrid_trip_km', 'Hybrid - Trip + KM'),

    ],
        string="Tariff Type",
        required=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=False,
        default=lambda self: self.env.company,
        tracking=True,
        index=True,
    )

    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    # --------------------------------------------------
    # EFFECTIVE DATES
    # --------------------------------------------------
    date_from = fields.Date(
        string="Effective From",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )

    date_to = fields.Date(
        string="Effective To",
        tracking=True,
        help="Leave empty for open-ended tariff"
    )

    # --------------------------------------------------
    # STANDARD PRICING
    # --------------------------------------------------
    rate = fields.Float(
        string="Rate",
        tracking=True,
        help="Generic fixed rate."
    )

    base_rate = fields.Float(
        string="Base Rate",
        tracking=True,
        help="Base amount before additional calculations."
    )

    per_km_rate = fields.Float(
        string="Per KM Rate",
        tracking=True,
        help="Rate charged per kilometer."
    )

    per_bin_rate = fields.Float(
        string="Per Bin Rate",
        tracking=True,
        help="Rate charged per bin."
    )

    per_trip_rate = fields.Float(
        string="Per Trip Rate",
        tracking=True,
        help="Rate charged per trip."
    )

    # --------------------------------------------------
    # FLAT RATE PRICING
    # --------------------------------------------------
    single_bin_price = fields.Float(
        string="Single Bin Price",
        tracking=True,
        help="Used when quantity = 1"
    )

    multiple_bin_price = fields.Float(
        string="Multiple Bin Price",
        tracking=True,
        help="Used when quantity > 1"
    )

    # --------------------------------------------------
    # TIERING
    # --------------------------------------------------
    min_bin_qty = fields.Integer(
        string="Minimum Bin Quantity",
        tracking=True,
    )

    max_bin_qty = fields.Integer(
        string="Maximum Bin Quantity",
        tracking=True,
    )

    min_distance = fields.Float(
        string="Minimum Distance",
        tracking=True,
        help="Minimum KM range."
    )

    max_distance = fields.Float(
        string="Maximum Distance",
        tracking=True,
        help="Maximum KM range."
    )

    # --------------------------------------------------
    # VALIDATIONS
    # --------------------------------------------------
    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(
                    _("Effective To date cannot be earlier than Effective From date.")
                )

    @api.constrains("code", "company_id", "date_from", "date_to", "active")
    def _check_overlapping_tariffs(self):
        """
        Prevent overlapping active tariffs for:
        - same company
        - same tariff code
        - overlapping date ranges
        """
        for rec in self:

            if not rec.active:
                continue

            domain = [
                ("id", "!=", rec.id),
                ("company_id", "=", rec.company_id.id),
                ("code", "=", rec.code),
                ("active", "=", True),
                "|",
                ("date_to", "=", False),
                ("date_to", ">=", rec.date_from),
            ]

            if rec.date_to:
                domain.append(("date_from", "<=", rec.date_to))

            if self.search_count(domain):
                raise ValidationError(_(
                    "An overlapping active transport tariff already exists for:\n"
                    "- Company: %(company)s\n"
                    "- Tariff Type: %(code)s\n\n"
                    "Please close the existing tariff or adjust the dates.",
                    company=rec.company_id.display_name,
                    code=rec.code,
                ))