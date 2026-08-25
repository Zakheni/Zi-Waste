"""Invoice line extensions carrying transport operational fields."""
from odoo import models, fields


class AccountMoveLine(models.Model):
    """Persist bin count, distance, trips, and weight on invoice lines."""
    _inherit = 'account.move.line'

    number_of_bins = fields.Integer(
        string="Number of Bins",
        default=0,
    )

    distance_km = fields.Float(
        string="Distance (KM)",
        default=0.0,
    )

    number_of_trips = fields.Integer(
        string="Trips",
        default=0,
    )

    weight_kg = fields.Float(
        string="Weight (KG)",
    )

    weight_ton = fields.Float(
        string="Weight (Ton)",
    )