from odoo import models
import psycopg2
from odoo import models, api, _
from odoo.exceptions import (ValidationError)

class FleetVehicleModelBrand(models.Model):
    _inherit = 'fleet.vehicle.model.brand'

    def init(self):
        super().init()
        self._cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            fleet_vehicle_model_brand_unique_name
            ON fleet_vehicle_model_brand (name)
            WHERE name IS NOT NULL
        """)

    @api.model_create_multi
    def create(self, vals_list):
        try:
            return super().create(vals_list)
        except psycopg2.errors.UniqueViolation as e:
            self._cr.rollback()
            if 'fleet_vehicle_model_brand_unique_name' in str(e):
                raise ValidationError(_(
                    'This vehicle brand already exists.'
                ))
            raise

    def write(self, vals):
        try:
            return super().write(vals)
        except psycopg2.errors.UniqueViolation as e:
            self._cr.rollback()
            if 'fleet_vehicle_model_brand_unique_name' in str(e):
                raise ValidationError(_(
                    'This vehicle brand already exists.'
                ))
            raise
