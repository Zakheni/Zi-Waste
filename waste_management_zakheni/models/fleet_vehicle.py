from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError
import psycopg2

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to Vehicle."))
        return super().unlink()

    def init(self):
        super().init()
        self._cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            fleet_vehicle_unique_plate_company
            ON fleet_vehicle (license_plate, company_id)
            WHERE license_plate IS NOT NULL
        """)
        self._cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            fleet_vehicle_unique_vin_company
            ON fleet_vehicle (vin_sn, company_id)
            WHERE vin_sn IS NOT NULL
        """)

    def create(self, vals_list):
        try:
            return super().create(vals_list)
        except psycopg2.errors.UniqueViolation as e:
            self._cr.rollback()
            self._raise_duplicate_error(e)

    def write(self, vals):
        try:
            return super().write(vals)
        except psycopg2.errors.UniqueViolation as e:
            self._cr.rollback()
            self._raise_duplicate_error(e)

    def _raise_duplicate_error(self, error):
        msg = str(error)

        if 'fleet_vehicle_unique_plate_company' in msg:
            raise ValidationError(_(
                'A vehicle with this License Plate already exists for this company.'
            ))
        elif 'fleet_vehicle_unique_vin_company' in msg:
            raise ValidationError(_(
                'A vehicle with this VIN already exists for this company.'
            ))
        else:
            raise ValidationError(_(
                'Duplicate vehicle detected. Please check your data.'
            ))

    service_request_id = fields.Many2one(
        'waste.service.request',
        string="Manifest",
        ondelete="set null"
    )
    planned_date = fields.Datetime(
        string="Planned Date",
        related="service_request_id.planned_date",
        store=True,
        readonly=True
    )
    driver_email = fields.Char(
        string="Driver Email",
        related='driver_id.email',
        store=True,  # optional but useful for searching / filtering
        readonly=True,
    )

    is_waste_tanker = fields.Boolean(
        string="Waste Tanker Truck",
        help="Tick if this vehicle has a fixed tank for liquid waste (e.g. 7000L, 9000L, etc.)."
    )

    tank_volume_id = fields.Many2one(
        'tank.volume',
        string="Tank Volume",
        help="Select the tank volume (e.g. 7000L, 9000L, etc.) for this truck."
    )

    # capacity_liters is now derived from tank.volume
    tank_capacity_liters = fields.Float(
        string="Tank Capacity (L)",
        related="tank_volume_id.capacity_liters",
        store=True,
        readonly=False,  # keep editable if you want to override per truck
    )

    busy_driver_ids = fields.Many2many(
        'res.partner',
        compute='_compute_busy_driver_ids',
        store=False,
    )


    @api.depends('driver_id')
    def _compute_busy_driver_ids(self):
        WSR = self.env['waste.service.request']
        now = fields.Datetime.now()

        busy_ids = set(WSR._get_busy_drivers_at_date(now))

        for vehicle in self:
            vehicle.busy_driver_ids = [(6, 0, list(busy_ids))]


class FleetVehicleModel(models.Model):
    _inherit = 'fleet.vehicle.model'

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to Vehicle Model."))
        return super().unlink()

    def init(self):
        super().init()
        self._cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            fleet_vehicle_model_unique_name_brand
            ON fleet_vehicle_model (name, brand_id)
            WHERE name IS NOT NULL
        """)

    @api.model_create_multi
    def create(self, vals_list):
        try:
            return super().create(vals_list)
        except psycopg2.errors.UniqueViolation as e:
            self._cr.rollback()
            if 'fleet_vehicle_model_unique_name_brand' in str(e):
                raise ValidationError(_(
                    'This vehicle model already exists for the selected brand.'
                ))
            raise

    def write(self, vals):
        try:
            return super().write(vals)
        except psycopg2.errors.UniqueViolation as e:
            self._cr.rollback()
            if 'fleet_vehicle_model_unique_name_brand' in str(e):
                raise ValidationError(_(
                    'This vehicle model already exists for the selected brand.'
                ))
            raise

    vehicle_type = fields.Selection(
        selection_add=[
            ('truck', 'Truck'),
            ('compactor', 'Compactor'),
            ('trailer', 'Trailer'),
            ('tank_truck', 'Tank Truck'),
        ],
        ondelete={
            'truck': 'set default',
            'compactor': 'set default',
            'trailer': 'set default',
            'tank_truck': 'set default',
        },
    )