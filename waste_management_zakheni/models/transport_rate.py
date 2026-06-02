from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class WasteTransportTariff(models.Model):
    _name = "waste.transport.tariff"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Transport Tariff Configuration"
    _rec_name = "name"
    _order = "company_id, rate_type, date_from desc"

    # --------------------------------------------------
    # BASIC INFO
    # --------------------------------------------------
    name = fields.Char(
        string="Tariff Name",
        required=True,
        tracking=True,
    )

    # company_id = fields.Many2one(
    #     "res.company",
    #     string="Company",
    #     default=lambda self: self.env.company,
    #     tracking=True,
    #     index=True,
    # )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=False,
        tracking=True,
        index=True,
    )

    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    # --------------------------------------------------
    # RATE TYPE
    # --------------------------------------------------
    rate_type = fields.Selection([

        ('flat', 'Flat Rate'),

        ('per_bin', 'Per Bin'),

        ('per_trip', 'Per Trip'),

        ('per_bin_km', 'Per Bin Per KM'),

        ('per_trip_km', 'Per Trip Per KM'),

        ('tier_bin', 'Tiered By Bin Count'),

        ('tier_distance', 'Tiered By Distance'),

        ('hybrid_bin_trip', 'Hybrid - Per Bin + Flat Trip'),

        ('hybrid_trip_km', 'Hybrid - Trip + KM'),

    ],
        string="Rate Type",
        required=True,
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
        help="Starting/base amount."
    )

    increment_rate = fields.Float(
        string="Increment Rate",
        tracking=True,
        help="Additional amount added when quantity increases."
    )

    per_bin_rate = fields.Float(
        string="Per Bin Rate",
        tracking=True,
        help="Rate charged per bin."
    )

    per_km_rate = fields.Float(
        string="Per KM Rate",
        tracking=True,
        help="Rate charged per kilometer."
    )

    per_trip_rate = fields.Float(
        string="Per Trip Rate",
        tracking=True,
        help="Rate charged per trip."
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
    )

    max_distance = fields.Float(
        string="Maximum Distance",
        tracking=True,
    )

    # --------------------------------------------------
    # VALIDATIONS
    # --------------------------------------------------
    @api.constrains("date_from", "date_to")
    def _check_date_range(self):

        for rec in self:

            if rec.date_to and rec.date_to < rec.date_from:

                raise ValidationError(_(
                    "Effective To date cannot be earlier than Effective From date."
                ))

    @api.constrains(
        "rate_type",
        "company_id",
        "date_from",
        "date_to",
        "active"
    )
    def _check_overlapping_tariffs(self):
        """
        Prevent overlapping active tariffs for:
        - same company
        - same rate type
        - overlapping date ranges

        EXCEPT:
        - tier_bin
        - tier_distance

        because tiering requires multiple rows.
        """

        for rec in self:

            if not rec.active:
                continue

            # -------------------------------------------------
            # SKIP TIERED TYPES
            # -------------------------------------------------
            if rec.rate_type in (
                    'tier_bin',
                    'tier_distance',
            ):
                continue

            domain = [

                ("id", "!=", rec.id),

                ("company_id", "=", rec.company_id.id),

                ("rate_type", "=", rec.rate_type),

                ("active", "=", True),

                "|",
                ("date_to", "=", False),
                ("date_to", ">=", rec.date_from),
            ]

            if rec.date_to:
                domain.append(
                    ("date_from", "<=", rec.date_to)
                )

            if self.search_count(domain):
                raise ValidationError(_(
                    "An overlapping active transport tariff already exists for:\n"
                    "- Company: %(company)s\n"
                    "- Rate Type: %(rate)s\n\n"
                    "Please close the existing tariff or adjust the dates.",

                    company=rec.company_id.display_name,

                    rate=rec.rate_type,
                ))

