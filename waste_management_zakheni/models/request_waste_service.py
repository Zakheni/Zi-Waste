from torch.library import _

from odoo import models, fields, api
from odoo.exceptions import UserError, AccessDenied, ValidationError


class WasteServiceRequest(models.Model):
    _name = 'waste.service.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Waste Service Request'

    name = fields.Char(
        string='Request ID',
        required=True,
        # copy=False,
        readonly=True,
        default='New')

    service_request_date = fields.Datetime(
        string='Service Request Date',
        default=fields.Datetime.now,  # use datetime imported from datetime
    )

    partner_id = fields.Many2one('res.partner', string="Customer", required=True)
    # pickup_point_id = fields.Many2one('pickup.point', string="Drop-off/Pickup Point", domain="[('partner_id', '=', partner_id)]")
    pickup_point_id = fields.Many2one('pickup.point', string="Drop-off/Pickup Point", related='sale_order_id.pickup_point_id')
    container_id = fields.Many2one('waste.container', string='Container')
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='pickup_point_id.partner_id',
        store=True,
        readonly=True
    )

    pickup_id = fields.Char(string="Pickup Point Name", related='pickup_point_id.name',)
    planned_date = fields.Datetime(string='Planned Date')

    quote_no = fields.Char(Strinh="Quote No.")
    service_description = fields.Text(string='Service Description')
    UN_No_SIN_No = fields.Char(string='UN No/SIN No')
    waste_profile_Data_sheet_No = fields.Char(string='Waste Profile/Data sheet No')
    DTNumber = fields.Char(string='DTNumber')
    disposal_side_id = fields.Many2one('waste.disposal.site', string="Disposal Side")
    driver_id = fields.Many2one( "hr.employee",string="Driver",)
    assistance_id = fields.Many2one("hr.employee", string="Driver Assistance")
    vehicle_id = fields.Many2one("fleet.vehicle", string="Vehicle Registration Number")
    trailer_id = fields.Many2one("fleet.vehicle", string="Trailer Registration Number")
    # capacity_tons = fields.Float(string='Captured Tons', related='disposal_side_id.capacity_tons')

    # busy_driver_ids = fields.Many2many(
    #     'hr.employee',
    #     compute="_compute_busy_drivers",
    #     store=True
    # )
    #
    # busy_assistance_ids = fields.Many2many(
    #     'hr.employee',
    #     compute="_compute_busy_assistants",
    #     store=True
    # )
    #
    # busy_track_ids = fields.Many2many(
    #     'fleet.vehicle',
    #     compute="_compute_busy_trucks",
    #     store=True
    # )
    #
    # busy_trailler_ids = fields.Many2many(
    #     'fleet.vehicle',
    #     compute="_compute_busy_traillers",
    #     store=True
    # )

    busy_driver_ids = fields.Many2many(
        'hr.employee',
        'waste_service_request_busy_driver_rel',  # unique relation table
        'request_id',  # FK to waste.service.request
        'employee_id',  # FK to hr.employee
        compute="_compute_busy_drivers",
        store=True,
        string="Busy Drivers"
    )

    busy_assistance_ids = fields.Many2many(
        'hr.employee',
        'waste_service_request_busy_assist_rel',  # different relation table
        'request_id',
        'employee_id',
        compute="_compute_busy_assistants",
        store=True,
        string="Busy Assistants"
    )

    busy_track_ids = fields.Many2many(
        'fleet.vehicle',
        'waste_service_request_busy_truck_rel',
        'request_id',
        'vehicle_id',
        compute="_compute_busy_trucks",
        store=True,
        string="Busy Trucks"
    )

    busy_trailler_ids = fields.Many2many(
        'fleet.vehicle',
        'waste_service_request_busy_trailer_rel',
        'request_id',
        'vehicle_id',
        compute="_compute_busy_traillers",
        store=True,
        string="Busy Trailers"
    )

    @api.depends('planned_date')
    def _compute_busy_drivers(self):
        now = fields.Datetime.now()
        for rec in self:
            busy = self.env['waste.service.request'].search([
                ('planned_date', '>=', now),
                ('driver_id', '!=', False),
                ('id', '!=', rec._origin.id or 0)  # ✅ safe check
            ]).mapped('driver_id').ids
            rec.busy_driver_ids = [(6, 0, busy)]

    @api.depends('planned_date')
    def _compute_busy_assistants(self):
        now = fields.Datetime.now()
        for rec in self:
            busy = self.env['waste.service.request'].search([
                ('planned_date', '>=', now),
                ('assistance_id', '!=', False),
                ('id', '!=', rec._origin.id or 0)
            ]).mapped('assistance_id').ids
            rec.busy_assistance_ids = [(6, 0, busy)]

    @api.depends('planned_date')
    def _compute_busy_trucks(self):
        now = fields.Datetime.now()
        for rec in self:
            busy = self.env['waste.service.request'].search([
                ('planned_date', '>=', now),
                ('vehicle_id', '!=', False),
                ('id', '!=', rec._origin.id or 0)
            ]).mapped('vehicle_id').ids
            rec.busy_track_ids = [(6, 0, busy)]

    @api.depends('planned_date')
    def _compute_busy_traillers(self):
        now = fields.Datetime.now()
        for rec in self:
            busy = self.env['waste.service.request'].search([
                ('planned_date', '>=', now),
                ('trailer_id', '!=', False),
                ('id', '!=', rec._origin.id or 0)
            ]).mapped('trailer_id').ids
            rec.busy_trailler_ids = [(6, 0, busy)]

    state = fields.Selection([
        ('draft', 'draft'),
        ('generated', 'Generated'),
        ('cancelled', 'Rejected'),
        ('done', 'Authorised'),
        ('none', 'None')
    ], default='draft')
    driver_signature = fields.Binary(string="Driver Signature")

    def action_signature(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Enter Signature',
            'res_model': 'driver.signature',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
            },
        }
    container_type = fields.Selection([
        ('bin', 'Bin'),
        ('tank', 'Tank'),
        ('none', 'None')
    ], String="Container Type", default=''
    )
    inUse = fields.Boolean(string='InUse', related='container_id.inUse', defauld=True)
    tank_ids = fields.Many2many('waste.container', 'waste_service_request_tanks_rel', string="Tanks")
    # Shunt
    shunt_from_id = fields.Many2one('pickup.point', string="From Location", domain="[('partner_id', '=', partner_id)]")
    shunt_to_id = fields.Many2one('pickup.point', string="To Location", domain="[('partner_id', '=', partner_id)]")
    lifted_bin_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_lifted_rel',  # Different relation table
        'request_id',
        'container_id',
        string="Lifted Bins"
    )
    dropped_bin_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_dropped_rel',  # Different relation table
        'request_id',
        'container_id',
        string="New Bins (Dropped)"
    )
    # Placement & Collection
    dropoff_container_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_containers_rel',
        string="Containers",
        )
    # Shunt
    shunt_container_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_shunt_rel',
        string="Containers",
    )
    # Shunt
    shunted_bin_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_shunted_rel',  # Different relation table
        'request_id',
        'container_id',
        string="Bins to Shunt"
    )

    @api.constrains('shunt_container_ids', 'dropoff_container_ids','lifted_bin_ids', 'product_uom_qty')
    def _check_bin_count(self):
        for rec in self:
            # Check shunting containers
            if rec.shunt_container_ids:
                shunt_count = len(rec.shunt_container_ids)
                if shunt_count != rec.product_uom_qty:
                    raise ValidationError(
                        f"Number of bins in Shunt Containers ({shunt_count}) "
                        f"must match Bin no. ({rec.product_uom_qty})."
                    )

            # Check drop-off containers
            if rec.dropoff_container_ids:
                dropoff_count = len(rec.dropoff_container_ids)
                if dropoff_count != rec.product_uom_qty:
                    raise ValidationError(
                        f"Number of bins = ({dropoff_count}) "
                        f"must match  Bin no. ({rec.product_uom_qty})."
                    )
            if rec.lifted_bin_ids:
                lifted_count = len(rec.lifted_bin_ids)
                if lifted_count != rec.product_uom_qty:
                    raise ValidationError(
                        f"Number of bins in Swap Containers ({lifted_count}) "
                        f"must match  Bin no. ({rec.product_uom_qty})."
                    )

    condition = fields.Selection([
        ('draft', 'draft'),
        ('done', 'Done')],
        string='Condition', default='draft')

    liters_collected = fields.Float(string="Liters Collected",)
    liters_remaining = fields.Float(string="Liters Remaining", compute="_compute_liters_remaining", store=True)

    sale_order_id = fields.Many2one('sale.order', string="Sales Order")

    @api.model
    def create(self, vals):
        # Handle sequence for name
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('waste.service.request') or 'New'

        record = super().create(vals)

        # Link driver to this service request
        if record.driver_id:
            record.driver_id.service_request_id = record.id

        # Link sale order to this service request
        if record.sale_order_id:
            record.sale_order_id.service_request_id = record.id

        return record

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            # Link driver to this service request
            if rec.driver_id:
                rec.driver_id.service_request_id = rec.id

            # Link sale order to this service request
            if rec.sale_order_id:
                rec.sale_order_id.service_request_id = rec.id

        return res
    @api.model
    def create(self, vals):
        # Handle sequence for name
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('waste.service.request') or 'New'

        record = super().create(vals)

        # Link to Sale Order if available
        if record.sale_order_id:
            record.sale_order_id.service_request_id = record.id

        return record
    #
    # @api.model
    # def write(self, vals):
    #     res = super().write(vals)
    #     for rec in self:
    #         if rec.sale_order_id:
    #             rec.sale_order_id.service_request_id = rec.id
    #     return res

    service_requested = fields.Selection([
        ('placement_of_bins', 'Placement of Bins'),
        ('shunting_of_bins', 'Shunting of Bins'),
        ('removal_of_bins', 'Removal of Bins'),
        ('waste_collection_&_disposal', 'Waste Collection & Disposal'),
        ('swapping_of_bins', 'Swapping of Bins'),
        ('none', 'None'),
    ], string="Service Requested")

    waste_type = fields.Selection([
        ('hazardous', 'Hazardous'),
        ('general_non-compactable', 'General Non-Compactable'),
        ('general_compactable', 'General Compactable'),
        ('none', 'None')
    ], string="Waste Type")

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

    ], string="Waste Details")

    bin_type = fields.Selection([
        ('6m³', '6m³'),
        ('9m³', '9m³'),
        ('11m³', '11m³'),
        ('18m³', '18m³'),
        ('28m³', '28m³'),
        ('none', 'None'),
    ], string="Bin Type" )

    tank_volume = fields.Selection([
        ('7000_liters', '7000 Liters'),
        ('9000_liters', '9000 Liters'),
        ('11000_liters', '11000 Liters'),
        ('12000_liters', '12000 Liters'),
        ('15000_liters', '15000 Liters'),
        ('none', 'None'),
    ], string="Tank Volume", related='tank_ids.tank_volume')

    product_id = fields.Many2one('product.product', string="Product")
    product_uom_qty = fields.Float(string="Quantity")
    price_unit = fields.Float(string="Unit Price")

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        for record in self:
            if record.sale_order_id and record.sale_order_id.order_line:
                line = record.sale_order_id.order_line[0]  # Pick the first order line, or loop through if needed

                record.product_id = line.product_id.id
                record.product_uom_qty = line.product_uom_qty
                record.price_unit = line.price_unit

                attribute_map = {
                    'container type': 'container_type',
                    'service requested': 'service_requested',
                    'waste type': 'waste_type',
                    'waste details': 'waste_details',
                    'bin type': 'bin_type',
                    'tank volume': 'tank_volume',
                }

                for field in attribute_map.values():
                    if hasattr(record, field):
                        setattr(record, field, False)

                for variant in line.product_id.product_template_attribute_value_ids:
                    attr_name = variant.attribute_id.name.lower()
                    attr_value = variant.product_attribute_value_id.name.lower().replace(" ", "_")
                    if attr_name in attribute_map:
                        field_name = attribute_map[attr_name]
                        if not getattr(record, field_name):
                            setattr(record, field_name, attr_value)


    @api.depends('liters_collected', 'tank_volume')
    def _compute_liters_remaining(self):
        for rec in self:
            try:
                total = float(rec.tank_volume.replace('L', '')) if rec.tank_volume else 0
            except:
                total = 0
            rec.liters_remaining = max(0.0, total - rec.liters_collected)

    def action_draft(self):
        self.state = 'draft'

    def action_generated(self):
        self.state = 'generated'
        for record in self:
            if record.state == 'generated':
                for container in record.dropoff_container_ids:
                    container.inUse = True
            elif record.state == 'generated':
                for lifted_bin in record.lifted_bin_ids:
                    lifted_bin.inUse = True
                for dropped_bin in record.dropped_bin_ids:
                    dropped_bin.inUse = True
            elif record.state == 'generated':
                for bin in record.shunt_container_ids:
                    bin.inUse = True
            elif record.state == 'generated':
                for container in record.dropoff_container_ids:
                    container.inUse = True
            elif record.state == 'generated':
                for container in record.dropoff_container_ids:
                    container.inUse = True
                for tank in record.tank_ids.filtered(lambda c: c.container_type == 'tank'):
                    tank.inUse = True

    def action_mark_done(self):

        for record in self:

            if record.service_requested == 'removal_of_bins':
                for container in record.dropoff_container_ids:
                    container.pickup_point_id = False
                    container.customer_id = False
                    container.inUse = False
                    container.status = 'un_use'
                    record.message_post(body=f"Removed bin: {container.name}")

            elif record.service_requested == 'swapping_of_bins':
                for lifted_bin in record.lifted_bin_ids:
                    from_name = record.pickup_point_id.name if record.pickup_point_id else 'Unknown'
                    lifted_bin.pickup_point_id = False
                    lifted_bin.customer_id = False
                    lifted_bin.inUse = False
                    lifted_bin.status = 'un_use'
                    record.message_post(body=f"Lifted bin '{lifted_bin.name}' from '{from_name}'")

                for dropped_bin in record.dropped_bin_ids:
                    to_name = record.pickup_point_id.name if record.pickup_point_id else 'Unknown'
                    dropped_bin.pickup_point_id = record.pickup_point_id
                    dropped_bin.customer_id = record.customer_id
                    dropped_bin.inUse = True
                    dropped_bin.status = 'in_use'
                    record.message_post(body=f"Dropped bin '{dropped_bin.name}' at '{to_name}'")

            elif record.service_requested == 'shunting_of_bins':
                from_name = record.shunt_from_id.name if record.shunt_from_id else 'Unknown'
                to_name = record.shunt_to_id.name if record.shunt_to_id else 'Unknown'
                for bin in record.shunt_container_ids:
                    bin.pickup_point_id = record.shunt_to_id
                    bin.inUse = True
                    bin.status = 'in_use'
                    record.message_post(
                        body=f"Shunted bin '{bin.name}' from '{from_name}' to '{to_name}'")

            elif record.service_requested == 'placement_of_bins':
                for container in record.dropoff_container_ids:
                    to_name = record.pickup_point_id.name if record.pickup_point_id else 'Unknown'
                    container.pickup_point_id = record.pickup_point_id
                    container.customer_id = record.customer_id
                    container.inUse = True
                    container.status = 'in_use'
                    record.message_post(body=f"Placed bin: {container.name} at {to_name}")

            elif record.service_requested == 'waste_collection_&_disposal':
                for container in record.dropoff_container_ids:
                    container.pickup_point_id = False
                    container.customer_id = False
                    container.inUse = False
                    container.status = 'un_use'
                    record.message_post(body=f"Collected & Disposed bin: {container.name}")

                for tank in record.tank_ids.filtered(lambda c: c.container_type == 'tank'):
                    to_name = record.pickup_point_id.name if record.pickup_point_id else 'Unknown'
                    tank.pickup_point_id = record.pickup_point_id
                    tank.customer_id = record.customer_id
                    tank.inUse = True
                    tank.status = 'un_use'
                    record.message_post(body=f"Collected & Emptied tank: {tank.name} ({tank.tank_volume})")

                    if record.service_type == 'collection' and record.container_type == 'tank':
                        record.tank_ids.write({
                            'liters_collected': record.liters_collected,
                            'liters_remaining': record.liters_remaining,
                        })

        self.state = 'done'

    def action_cancelled(self):
        self.state = 'cancelled'

    def action_open_related_sales(self):
        """Redirect to sales orders related to this customer"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Orders',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'target': 'current',
        }

    # # Schedule information
    # driver_id = fields.Many2one('res.users', string='Driver')
    # assistance_id = fields.Many2one('res.users', string='Driver Assistance')
    # vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle Registration Number', )
    # trailer_id = fields.Char(string="Trailer Registration Number")
    #
    # # Delivery information
    # arrival_time = fields.Datetime(string='Arrival Time')
    # departure_time = fields.Datetime(string='Departure Time')
    # kilometers = fields.Integer(string='Kilometers')
    #
    # # Capture information
    # return_date = fields.Datetime(string='Return Date')
    # capacity_tons = fields.Float(string='Captured Tons')
    # comment = fields.Text(string='Comment')

    # Documents upload
    manifest_document = fields.Binary("Manifests Document", attachment=True)
    manifest_document_filename = fields.Char()

    weighbridge_slip = fields.Binary("Weighbridge Slip", attachment=True)
    weighbridge_slip_filename = fields.Char()

    safety_certificate = fields.Binary("Safety Certificate", attachment=True)
    safety_certificate_filename = fields.Char()

    def action_open_manifest_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Manifest Document',
            'res_model': 'waste.service.request',
            'view_mode': 'form',
            'view_id': self.env.ref('waste_management_zakheni.view_manifest_document_popup').id,
            'res_id': self.id,
            'target': 'new',
        }

    def action_open_weighbridge_slip(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Weighbridge Slip',
            'res_model': 'waste.service.request',
            'view_mode': 'form',
            'view_id': self.env.ref('waste_management_zakheni.view_weighbridge_slip_popup').id,
            'res_id': self.id,
            'target': 'new',
        }

    def action_open_safety_certificate(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Safety Certificate',
            'res_model': 'waste.service.request',
            'view_mode': 'form',
            'view_id': self.env.ref('waste_management_zakheni.view_safety_certificate_popup').id,
            'res_id': self.id,
            'target': 'new',
        }

    # SCHEDULE
    schedule_ids = fields.One2many(
        "waste.schedule", "service_request_id", string="Schedules"
    )
    schedule_count = fields.Integer(
        string="Schedules", compute="_compute_schedule_count"
    )

    latest_driver_id = fields.Many2one("hr.employee", string="Driver", compute="_compute_latest_schedule", store=True)
    latest_assistance_id = fields.Many2one("hr.employee", string="Driver Assistance", compute="_compute_latest_schedule",
                                           store=True)
    latest_vehicle_id = fields.Many2one("fleet.vehicle", string="Vehicle Registration Number",
                                        compute="_compute_latest_schedule", store=True)
    latest_trailer_id = fields.Many2one("fleet.vehicle", string="Trailer Registration Number", compute="_compute_latest_schedule",
                                    store=True)

    def _compute_schedule_count(self):
        for rec in self:
            rec.schedule_count = len(rec.schedule_ids)

    @api.depends("schedule_ids")
    def _compute_latest_schedule(self):
        for rec in self:
            if rec.schedule_ids:
                latest = rec.schedule_ids[-1]  # last created schedule
                rec.latest_driver_id = latest.driver_id
                rec.latest_assistance_id = latest.assistance_id
                rec.latest_vehicle_id = latest.vehicle_id
                rec.latest_trailer_id = latest.trailer_id
            else:
                rec.latest_driver_id = False
                rec.latest_assistance_id = False
                rec.latest_vehicle_id = False
                rec.latest_trailer_id = False

    def action_view_schedules(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Schedules",
            "res_model": "waste.schedule",
            "view_mode": "tree,form",
            "domain": [("service_request_id", "=", self.id)],
            "context": {"default_service_request_id": self.id},
        }

    # DELIVERY
    delivery_ids = fields.One2many(
        "waste.delivery", "service_request_id", string="Deliveries"
    )
    delivery_count = fields.Integer(
        string="Deliveries", compute="_compute_delivery_count"
    )

    latest_arrival_time = fields.Datetime(string='Arrival Time', compute="_compute_latest_delivery", store=True)
    latest_departure_time = fields.Datetime(string='Departure Time', compute="_compute_latest_delivery", store=True)
    latest_kilometers = fields.Integer(string='Kilometers', compute="_compute_latest_delivery", store=True)
    latest_quantity_collected = fields.Float(string='Quantity Collected',  compute="_compute_latest_delivery", store=True)

    def _compute_delivery_count(self):
        for rec in self:
            rec.delivery_count = len(rec.delivery_ids)

    @api.depends("delivery_ids")
    def _compute_latest_delivery(self):
        for rec in self:
            if rec.delivery_ids:
                latest = rec.delivery_ids[-1]  # last created schedule
                rec.latest_arrival_time = latest.arrival_time
                rec.latest_departure_time = latest.departure_time
                rec.latest_kilometers = latest.kilometers
                rec.latest_quantity_collected = latest.quantity_collected
            else:
                rec.latest_arrival_time = False
                rec.latest_departure_time = False
                rec.latest_kilometers = False
                rec.latest_quantity_collected = False

    def action_view_deliveries(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Deliveries",
            "res_model": "waste.delivery",
            "view_mode": "tree,form",
            "domain": [("service_request_id", "=", self.id)],
            "context": {"default_service_request_id": self.id},
        }

    #CAPTURES
    capture_ids = fields.One2many(
        "waste.capture", "service_request_id", string="Captures"
    )
    capture_count = fields.Integer(
        string="Captures", compute="_compute_capture_count"
    )

    latest_return_date = fields.Datetime(string='Return Date', compute="_compute_latest_capture", store=True)
    latest_capacity_tons = fields.Float(string='Captured Tons', compute="_compute_latest_capture", store=True)
    latest_unit_of_measure = fields.Many2one('uom.uom', string='Units of Measure', compute="_compute_latest_capture", store=True)
    latest_driver_signature = fields.Binary(string="Driver Signature",compute="_compute_latest_capture", store=True)

    def _compute_capture_count(self):
        for rec in self:
            rec.capture_count = len(rec.capture_ids)

    @api.depends("capture_ids")
    def _compute_latest_capture(self):
        for rec in self:
            if rec.capture_ids:
                latest = rec.capture_ids[-1]  # last created schedule
                rec.latest_return_date = latest.return_date
                rec.latest_capacity_tons = latest.capacity_tons
                rec.latest_unit_of_measure = latest.unit_of_measure
                rec.latest_driver_signature = latest.driver_signature
            else:
                rec.latest_return_date = False
                rec.latest_capacity_tons = False
                rec.latest_unit_of_measure = False
                rec.latest_driver_signature = False

    def action_view_captures(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Captures",
            "res_model": "waste.capture",
            "view_mode": "tree,form",
            "domain": [("service_request_id", "=", self.id)],
            "context": {"default_service_request_id": self.id},
        }

    # UPLOADS
    upload_ids = fields.One2many(
        "waste.upload", "service_request_id", string="Uploads"
    )
    upload_count = fields.Integer(
        string="Uploads", compute="_compute_uploads_count"
    )

    latest_manifest_document = fields.Binary("Manifests Document", compute="_compute_latest_upload", store=True, attachment=True)
    latest_manifest_document_filename = fields.Char()

    latest_weighbridge_slip = fields.Binary("Weighbridge Slip", compute="_compute_latest_upload", store=True, attachment=True)
    latest_weighbridge_slip_filename = fields.Char()

    latest_safety_certificate = fields.Binary("Safety Certificate", compute="_compute_latest_upload", store=True, attachment=True)
    latest_safety_certificate_filename = fields.Char()

    def _compute_uploads_count(self):
        for rec in self:
            rec.upload_count = len(rec.upload_ids)

    @api.depends("upload_ids")
    def _compute_latest_upload(self):
        for rec in self:
            if rec.upload_ids:
                latest = rec.upload_ids[-1]  # last created schedule
                rec.latest_manifest_document = latest.manifest_document
                rec.latest_weighbridge_slip = latest.weighbridge_slip
                rec.latest_safety_certificate = latest.safety_certificate

            else:
                rec.latest_manifest_document = False
                rec.latest_weighbridge_slip = False
                rec.latest_safety_certificate = False

    def action_view_uploads(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Uploads",
            "res_model": "waste.upload",
            "view_mode": "tree,form",
            "domain": [("service_request_id", "=", self.id)],
            "context": {"default_service_request_id": self.id},
        }

# WORKSHEET
    worksheet_ids = fields.One2many(
        "waste.worksheet", "service_request_id", string="Worksheet"
    )
    worksheet_count = fields.Integer(
        string="Worksheet", compute="_compute_worksheets_count"
    )

    latest_worksheet_arrival_time = fields.Datetime(string='Arrival Time', compute="_compute_latest_worksheet", store=True)
    latest_worksheet_kilometers = fields.Integer(string='Kilometers', compute="_compute_latest_worksheet", store=True)
    latest_worksheet_return_date = fields.Datetime(string='Return Date', compute="_compute_latest_worksheet", store=True)
    latest_worksheet_unit_of_measure = fields.Many2one('uom.uom', string='Units of Measure',
                                                       compute="_compute_latest_worksheet",
                                                       store=True)
    latest_worksheet_quantity_collected = fields.Float(string='Quantity Collected', compute="_compute_latest_worksheet",
                                             store=True)
    latest_worksheet_driver_signature = fields.Binary(string="Signature", compute="_compute_latest_capture", store=True)
    latest_worksheet_manifest_document = fields.Binary("Manifests Document", compute="_compute_latest_worksheet", store=True, attachment=True)
    latest_worksheet_manifest_document_filename = fields.Char()

    latest_worksheet_weighbridge_slip = fields.Binary("Weighbridge Slip", compute="_compute_latest_worksheet", store=True, attachment=True)
    latest_worksheet_weighbridge_slip_filename = fields.Char()

    latest_worksheet_safety_certificate = fields.Binary("Safety Certificate", compute="_compute_latest_worksheet", store=True, attachment=True)
    latest_worksheet_safety_certificate_filename = fields.Char()

    def _compute_worksheets_count(self):
        for rec in self:
            rec.worksheet_count = len(rec.worksheet_ids)

    @api.depends("worksheet_ids")
    def _compute_latest_worksheet(self):
        for rec in self:
            if rec.worksheet_ids:
                latest = rec.worksheet_ids[-1]  # last created schedule
                rec.latest_worksheet_arrival_time = latest.arrival_time
                rec.latest_worksheet_kilometers = latest.kilometers
                rec.latest_worksheet_return_date = latest.return_date
                rec.latest_worksheet_unit_of_measure = latest.unit_of_measure
                rec.latest_worksheet_quantity_collected = latest.quantity_collected
                rec.latest_worksheet_driver_signature = latest.driver_signature
                rec.latest_worksheet_manifest_document = latest.manifest_document
                rec.latest_worksheet_weighbridge_slip = latest.weighbridge_slip
                rec.latest_worksheet_safety_certificate = latest.safety_certificate

            else:
                rec.latest_worksheet_arrival_time = False
                rec.latest_worksheet_kilometers = False
                rec.latest_worksheet_return_date = False
                rec.latest_worksheet_unit_of_measure = False
                rec.latest_worksheet_quantity_collected = False
                rec.latest_worksheet_driver_signature = False
                rec.latest_worksheet_manifest_document = False
                rec.latest_worksheet_weighbridge_slip = False
                rec.latest_worksheet_safety_certificate = False

    def action_view_worksheet(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Worksheet",
            "res_model": "waste.worksheet",
            "view_mode": "tree,form",
            "domain": [("service_request_id", "=", self.id)],
            "context": {"default_service_request_id": self.id},
        }



class SaleOrder(models.Model):
    _inherit = 'sale.order'

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

    pickup_point_id = fields.Many2one(
        'pickup.point',
        string="Drop-off/Pickup Point",
        domain="[('partner_id', '=', partner_id)]",
        required=True
    )

    pickup_point_ids = fields.One2many(
        'pickup.point', 'sale_order_id',
        string="Drop-off/Pickup Point",
        domain="[('partner_id', '=', partner_id)]",
        required=True
    )

    container_ids = fields.One2many('waste.container', 'sale_order_id', string="Waste Containers")


class HREmployee(models.Model):
    _inherit = 'hr.employee'

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


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

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