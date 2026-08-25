# models/waste_schedule.py
"""Waste service scheduling records."""
from odoo import models, fields, api

class WasteSchedule(models.Model):
    """Plan and track scheduled waste collection windows."""
    _name = "waste.schedule"
    _description = "Waste Schedule"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "driver_id"

    service_request_id = fields.Many2one(
        "waste.service.request",
        string="Service Request",
        ondelete="set null"
    )
    driver_id = fields.Many2one(
        "hr.employee",
        string="Driver",
       )
    assistance_id = fields.Many2one("hr.employee", string="Driver Assistance")
    vehicle_id = fields.Many2one("fleet.vehicle", string="Vehicle Registration Number")
    trailer_id = fields.Many2one("fleet.vehicle", string="Trailer Registration Number")
    planned_date = fields.Datetime(string='Planned Date', related='service_request_id.planned_date', store=True)

    partner_id = fields.Many2one('res.partner', string="Customer", related='service_request_id.partner_id')
    pickup_point_id = fields.Many2one('pickup.point', string="Drop-off/Pickup Point", related='service_request_id.pickup_point_id')

    service_requested = fields.Selection([
        ('placement_of_bins', 'Placement of Bins'),
        ('shunting_of_bins', 'Shunting of Bins'),
        ('removal_of_bins', 'Removal of Bins'),
        ('waste_collection_&_disposal', 'Waste Collection & Disposal'),
        ('swapping_of_bins', 'Swapping of Bins'),
        ('none', 'None'),
    ], string="Service Requested", related='service_request_id.service_requested')

    waste_type = fields.Selection([
        ('hazardous', 'Hazardous'),
        ('general_non-compactable', 'General Non-Compactable'),
        ('general_compactable', 'General Compactable'),
        ('none', 'None')
    ], string="Waste Type", related='service_request_id.waste_type')

    waste_details = fields.Selection([
        ('recyclable', 'Recyclable'),
        ('non-recyclable', 'Non-Recyclable'),
        ('ammonium_nitrate', 'Ammonium Nitrate'),
        ('used_coal', 'Used Coal'),
        ('computer_waste', 'Computer Waste'),
        ('general_waste', 'General Waste'),
        ('chemical', 'Chemical'),
        ('sulphur', 'Sulphur'),
        ('rubber', 'Rubber'),
        ('copper_sulphide', 'Copper Sulphide'),
        ('hazardous', 'Hazardous'),
        ('none', 'None'),

    ], string="Waste Details", related='service_request_id.waste_details')

    bin_type = fields.Selection([
        ('6m³', '6m³'),
        ('9m³', '9m³'),
        ('11m³', '11m³'),
        ('18m³', '18m³'),
        ('28m³', '28m³'),
        ('none', 'None'),
    ], string="Bin Type", related='service_request_id.bin_type')

    tank_volume = fields.Selection([
        ('7000_liters', '7000 Liters'),
        ('9000_liters', '9000 Liters'),
        ('11000_liters', '11000 Liters'),
        ('12000_liters', '12000 Liters'),
        ('15000_liters', '15000 Liters'),
        ('none', 'None'),
    ], string="Tank Volume", related='service_request_id.tank_volume')
    container_type = fields.Selection([
        ('bin', 'Bin'),
        ('tank', 'Tank'),
        ('none', 'None')
    ], String="Container Type", default='', related='service_request_id.container_type'
    )
    inUse = fields.Boolean(string='InUse', related='service_request_id.inUse', defauld=True, )
    tank_ids = fields.Many2many('waste.container', 'waste_service_request_tanks_rel', string="Tanks", related='service_request_id.tank_ids')
    # Shunt
    shunt_from_id = fields.Many2one('pickup.point', string="From Location", domain="[('partner_id', '=', partner_id)]", related='service_request_id.shunt_from_id')
    shunt_to_id = fields.Many2one('pickup.point', string="To Location", domain="[('partner_id', '=', partner_id)]", related='service_request_id.shunt_to_id')

    lifted_bin_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_lifted_rel',  # Different relation table
        'request_id',
        'container_id',
        string="Lifted Bins" , related='service_request_id.lifted_bin_ids'
    )
    dropped_bin_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_dropped_rel',  # Different relation table
        'request_id',
        'container_id',
        string="New Bins (Dropped)",
        related='service_request_id.dropped_bin_ids'
    )
    # Placement & Collection
    dropoff_container_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_containers_rel',
        string="Containers",
        related='service_request_id.dropoff_container_ids'
        )
    # Shunt
    shunt_container_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_shunt_rel',
        string="Containers",
        related='service_request_id.shunt_container_ids'
    )
    # Shunt
    shunted_bin_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_shunted_rel',  # Different relation table
        'request_id',
        'container_id',
        string="Bins to Shunt",
        related='service_request_id.shunted_bin_ids'
    )

    state = fields.Selection([
        ("draft", "Draft"),
        ('scheduled', 'Scheduled'),
    ], string="Status", default="draft", required=True, )

    busy_driver_ids = fields.Many2many(
        'hr.employee',
        compute="_compute_busy_drivers",
        store=False
    )

    busy_assistance_ids = fields.Many2many(
        'hr.employee',
        compute="_compute_busy_assistants",
        store=False
    )

    busy_track_ids = fields.Many2many(
        'fleet.vehicle',
        compute="_compute_busy_trucks",
        store=False
    )

    busy_trailler_ids = fields.Many2many(
        'fleet.vehicle',
        compute="_compute_busy_traillers",
        store=False
    )

    @api.depends('planned_date')
    def _compute_busy_drivers(self):
        now = fields.Datetime.now()
        for rec in self:
            busy = self.env['waste.schedule'].search([
                ('planned_date', '>=', now),
                ('driver_id', '!=', False),
                ('id', '!=', rec._origin.id or 0)  # ✅ safe check
            ]).mapped('driver_id').ids
            rec.busy_driver_ids = [(6, 0, busy)]

    @api.depends('planned_date')
    def _compute_busy_assistants(self):
        now = fields.Datetime.now()
        for rec in self:
            busy = self.env['waste.schedule'].search([
                ('planned_date', '>=', now),
                ('assistance_id', '!=', False),
                ('id', '!=', rec._origin.id or 0)
            ]).mapped('assistance_id').ids
            rec.busy_assistance_ids = [(6, 0, busy)]

    @api.depends('planned_date')
    def _compute_busy_trucks(self):
        now = fields.Datetime.now()
        for rec in self:
            busy = self.env['waste.schedule'].search([
                ('planned_date', '>=', now),
                ('vehicle_id', '!=', False),
                ('id', '!=', rec._origin.id or 0)
            ]).mapped('vehicle_id').ids
            rec.busy_track_ids = [(6, 0, busy)]

    @api.depends('planned_date')
    def _compute_busy_traillers(self):
        now = fields.Datetime.now()
        for rec in self:
            busy = self.env['waste.schedule'].search([
                ('planned_date', '>=', now),
                ('trailer_id', '!=', False),
                ('id', '!=', rec._origin.id or 0)
            ]).mapped('trailer_id').ids
            rec.busy_trailler_ids = [(6, 0, busy)]

    # @api.depends('planned_date')
    # def _compute_busy_drivers(self):
    #     now = fields.Datetime.now()
    #     busy = self.env['waste.schedule'].search([
    #         ('planned_date', '>=', now),
    #         ('driver_id', '!=', False),
    #         ('id', '!=', self.id)
    #     ]).mapped('driver_id').ids
    #     for rec in self:
    #         rec.busy_driver_ids = [(6, 0, busy)]
    #
    # @api.depends('planned_date')
    # def _compute_busy_assistants(self):
    #     now = fields.Datetime.now()
    #     busy = self.env['waste.schedule'].search([
    #         ('planned_date', '>=', now),
    #         ('assistance_id', '!=', False),
    #         ('id', '!=', self.id)
    #     ]).mapped('assistance_id').ids
    #     for rec in self:
    #         rec.busy_assistance_ids = [(6, 0, busy)]
    #
    # @api.depends('planned_date')
    # def _compute_busy_trucks(self):
    #     now = fields.Datetime.now()
    #     busy = self.env['waste.schedule'].search([
    #         ('planned_date', '>=', now),
    #         ('vehicle_id', '!=', False),
    #         ('id', '!=', self.id)
    #     ]).mapped('vehicle_id').ids
    #     for rec in self:
    #         rec.busy_track_ids = [(6, 0, busy)]
    #
    # @api.depends('planned_date')
    # def _compute_busy_traillers(self):
    #     now = fields.Datetime.now()
    #     busy = self.env['waste.schedule'].search([
    #         ('planned_date', '>=', now),
    #         ('trailer_id', '!=', False),
    #         ('id', '!=', self.id)
    #     ]).mapped('trailer_id').ids
    #     for rec in self:
    #         rec.busy_trailler_ids = [(6, 0, busy)]

    # ----------------------
    # Button Actions
    # ----------------------
    def action_set_to_draft(self):
        self.state = "draft"

    def action_set_to_scheduled(self):
        for rec in self:
            rec.state = "scheduled"
            if rec.service_request_id:
                rec.service_request_id.state = "scheduled"

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if record.driver_id and record.service_request_id:
            record.driver_id.service_request_id = record.service_request_id.id
        return record

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.driver_id and rec.service_request_id:
                rec.driver_id.service_request_id = rec.service_request_id.id
        return res