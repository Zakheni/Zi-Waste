from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TankTariff(models.Model):
    _name = "waste.tank.tariff"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Tank Tariff Configuration"
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

    code = fields.Char(
        string="Tariff Code",
        required=True,
        tracking=True,
        help="Internal code e.g. septic, grease"
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
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
    # PRICING
    # --------------------------------------------------
    base_kl = fields.Float(
        string="Base kL",
        default=4.0,
        required=True,
        tracking=True,
    )

    base_price = fields.Float(
        string="Base Price",
        required=True,
        tracking=True,
    )

    extra_rate = fields.Float(
        string="Extra Rate per kL",
        required=True,
        tracking=True,
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
                    "An overlapping active tariff already exists for:\n"
                    "- Company: %(company)s\n"
                    "- Tariff Code: %(code)s\n\n"
                    "Please close the existing tariff or adjust the dates.",
                    company=rec.company_id.display_name,
                    code=rec.code,
                ))


# from odoo import models, fields
#
# class TankTariff(models.Model):
#     _name = "waste.tank.tariff"
#     _inherit = ['mail.thread', 'mail.activity.mixin']
#     _description = "Tank Tariff Configuration"
#     _rec_name = "name"
#
#     name = fields.Char(
#         string="Tariff Name",
#         required=True,
#         tracking=True,
#     )
#
#     code = fields.Char(
#         string="Tariff Code",
#         required=True,
#         tracking=True,
#         help="Internal code e.g. septic, grease"
#     )
#
#     base_kl = fields.Float(
#         string="Base kL",
#         default=4.0,
#         required=True,
#         tracking=True,
#     )
#
#     base_price = fields.Float(
#         string="Base Price",
#         required=True,
#         tracking=True,
#     )
#
#     extra_rate = fields.Float(
#         string="Extra Rate per kL",
#         required=True,
#         tracking = True,
#     )
#
#     active = fields.Boolean(default=True, tracking=True,)
