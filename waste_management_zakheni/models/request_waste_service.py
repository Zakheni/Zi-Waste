import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError
from .service_provider import SA_PROVINCES

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
    pickup_point_id = fields.Many2one('pickup.point', string="Pickup Point", ondelete='cascade')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    service_request_date = fields.Datetime(
        string='Service Request Date',
        default=fields.Datetime.now,  # use datetime imported from datetime
    )

    partner_id = fields.Many2one('res.partner', string="Customer",)

    pickup_point_ids = fields.One2many(
        'pickup.point',
        'service_request_id',
        string="Drop-off/Pickup Points",
        store=True,
    )

    container_id = fields.Many2one('waste.container', string='Container')
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='pickup_point_id.partner_id',
        store=True,
        readonly=True
    )

    pickup_id = fields.Char(string="Pickup Point Name", related='pickup_point_id.name',)
    planned_date = fields.Datetime(string='Planned Date', )

    quote_no = fields.Char(Strinh="Quote No.")
    service_description = fields.Text(string='Service Description')
    UN_No_SIN_No = fields.Char(string='UN No/SIN No')
    waste_profile_Data_sheet_No = fields.Char(string='Waste Profile/Data sheet No')
    DTNumber = fields.Char(string='DTNumber')
    disposal_site_id = fields.Many2one('waste.disposal.site', string="Disposal Side")
    driver_id = fields.Many2one( "hr.employee",string="Driver", )
    assistance_id = fields.Many2one("hr.employee", string="Driver Assistance")
    vehicle_id = fields.Many2one("fleet.vehicle", string="Vehicle Registration Number")
    trailer_id = fields.Many2one("fleet.vehicle", string="Trailer Registration Number")
    driver_signature = fields.Binary(string="Driver Signature")

    is_rejected = fields.Boolean(
        string="Ever Rejected",
        default=False,
        tracking=True,
        help="Ticked automatically if this request has ever been rejected.",
    )
    reject_reason = fields.Text(string="Enter Reject Reason", tracking=True,  store=True)
    amend_comment = fields.Text(string="Enter Amend Comment", tracking=True, store=True)
    driver_work_email = fields.Char(string="Driver Work email", related="driver_id.work_email", store=True)

    busy_driver_ids = fields.Many2many(
        'hr.employee',
        'waste_service_request_busy_driver_rel',
        'request_id',
        'employee_id',
        compute="_compute_busy_drivers",
        store=False,  # <-- changed from True
        string="Busy Drivers"
    )

    busy_assistance_ids = fields.Many2many(
        'hr.employee',
        'waste_service_request_busy_assist_rel',
        'request_id',
        'employee_id',
        compute="_compute_busy_assistants",
        store=False,  # <-- changed
        string="Busy Assistants"
    )

    busy_track_ids = fields.Many2many(
        'fleet.vehicle',
        'waste_service_request_busy_truck_rel',
        'request_id',
        'vehicle_id',
        compute="_compute_busy_trucks",
        store=False,  # <-- changed
        string="Busy Trucks"
    )

    busy_trailler_ids = fields.Many2many(
        'fleet.vehicle',
        'waste_service_request_busy_trailer_rel',
        'request_id',
        'vehicle_id',
        compute="_compute_busy_traillers",
        store=False,  # <-- changed
        string="Busy Trailers"
    )

    # Checkbox (optional – if you already have it, keep yours)
    is_service_provider = fields.Boolean(string='Use Service Provider?')

    # Selected service provider
    provider_id = fields.Many2one('wms.service.provider', string="Service Provider")

    provider_name = fields.Char(
        string="Name",
        related='provider_id.name',
        store=True,
        readonly=True,
    )
    provider_province = fields.Selection(
        SA_PROVINCES,
        string="Province",
        related='provider_id.province',
        store=True,
        readonly=True,
    )
    provider_city = fields.Char(
        string="City",
        related='provider_id.city',
        store=True,
        readonly=True,
    )
    provider_suburb = fields.Char(
        string="Suburb",
        related='provider_id.suburb',
        store=True,
        readonly=True,
    )
    provider_phone = fields.Char(
        string="Phone",
        related='provider_id.phone',
        readonly=True,
    )
    provider_mobile = fields.Char(
        string="Mobile",
        related='provider_id.mobile',
        readonly=True,
    )
    provider_email = fields.Char(
        string="Email",
        related='provider_id.email',
        readonly=True,
    )

    def action_open_simple_provider_wizard(self):
        """
        Open the provider-search wizard for this waste.service.request.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Find Service Provider',
            'res_model': 'waste.request.provider.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'waste.service.request',
                'active_id': self.id,
            },
        }

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
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('scheduled', 'Scheduled'),
        ('assigned', 'Assigned to Driver'),
        ('dispatched', 'Dispatched'),
        ('service_delivered', 'Service Delivered'),
        ('cancelled', 'Rejected'),
        ('done', 'Authorised'),
        ('none', 'None'),
    ], default='draft', tracking=True)

    @api.constrains("state", "planned_date", "driver_id", "vehicle_id", "wizard_pickup_point_ids")
    def _check_required_fields_in_states(self):
        for rec in self:
            # Required when scheduled
            if rec.state == "scheduled":
                if not rec.planned_date:
                    raise ValidationError(_("Please Enter Planned Date."))
                # if not rec.driver_id:
                #     raise ValidationError(_("Please Enter Driver."))
                # if not rec.vehicle_id:
                #     raise ValidationError(_("Please Enter Vehicle."))

            # Required when generated
            if rec.state == "generated":
                if not rec.wizard_pickup_point_ids:
                    raise ValidationError(_("Please select Pickup/Drop Off Point(s)."))

    @api.model
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

#======================================================
#BIB COUNT VERIFICATION
#=====================================================
# @api.constrains('shunt_container_ids', 'dropoff_container_ids','lifted_bin_ids', 'product_uom_qty')
# def _check_bin_count(self):
#     for rec in self:
#         # Check shunting containers
#         if rec.shunt_container_ids:
#             shunt_count = len(rec.shunt_container_ids)
#             if shunt_count != rec.product_uom_qty:
#                 raise ValidationError(
#                     f"Number of bins in Shunt Containers ({shunt_count}) "
#                     f"must match Bin no. ({rec.product_uom_qty})."
#                 )
#
#         # Check drop-off containers
#         if rec.dropoff_container_ids:
#             dropoff_count = len(rec.dropoff_container_ids)
#             if dropoff_count != rec.product_uom_qty:
#                 raise ValidationError(
#                     f"Number of bins = ({dropoff_count}) "
#                     f"must match  Bin no. ({rec.product_uom_qty})."
#                 )
#         if rec.lifted_bin_ids:
#             lifted_count = len(rec.lifted_bin_ids)
#             if lifted_count != rec.product_uom_qty:
#                 raise ValidationError(
#                     f"Number of bins in Swap Containers ({lifted_count}) "
#                     f"must match  Bin no. ({rec.product_uom_qty})."
#                 )


    condition = fields.Selection([
        ('draft', 'draft'),
        ('done', 'Done')],
        string='Condition', default='draft')

    liters_collected = fields.Float(string="Liters Collected",)
    liters_remaining = fields.Float(string="Liters Remaining", compute="_compute_liters_remaining", store=True)

    sale_order_id = fields.Many2one('sale.order', string="Sales Order")

    # @api.model
    # def create(self, vals):
    #     # Handle sequence for name
    #     if vals.get('name', 'New') == 'New':
    #         vals['name'] = self.env['ir.sequence'].next_by_code('waste.service.request') or 'New'
    #
    #     record = super().create(vals)
    #
    #     # Link driver to this service request
    #     if record.driver_id:
    #         record.driver_id.service_request_id = record.id
    #
    #     # Link sale order to this service request
    #     if record.sale_order_id:
    #         record.sale_order_id.service_request_id = record.id
    #
    #     return record
    #
    # def write(self, vals):
    #     res = super().write(vals)
    #     for rec in self:
    #         # Link driver to this service request
    #         if rec.driver_id:
    #             rec.driver_id.service_request_id = rec.id
    #
    #         # Link sale order to this service request
    #         if rec.sale_order_id:
    #             rec.sale_order_id.service_request_id = rec.id
    #
    #     return res

    # Link to your config tables (which link to product.attribute.value)
    service_requested_id = fields.Many2one('service.request', string="Service Requested")
    waste_type_id = fields.Many2one('waste.type', string="Waste Type")
    waste_details_id = fields.Many2one('waste.details', string="Waste Details")
    bin_type_id = fields.Many2one('bin.type', string="Bin Type")
    container_type_id = fields.Many2one('container.type', string="Container Type")
    tank_volume_id = fields.Many2one('tank.volume', related='tank_ids.tank_volume_id', string="Tank Volume")

    hide_waste_type = fields.Boolean(compute='_compute_field_visibility')
    hide_waste_details = fields.Boolean(compute='_compute_field_visibility')
    hide_droppoff_container_ids_placement = fields.Boolean(compute='_compute_field_visibility')
    hide_droppoff_container_ids_removal = fields.Boolean(compute='_compute_field_visibility')
    hide_droppoff_container_ids_collection = fields.Boolean(compute='_compute_field_visibility')
    hide_droppoff_container_ids_is_bin = fields.Boolean(compute='_compute_field_visibility')
    hide_lifted_bin_ids_swap = fields.Boolean(compute='_compute_field_visibility')
    hide_dropped_bin_ids_swap = fields.Boolean(compute='_compute_field_visibility')
    hide_dropped_to_swap = fields.Boolean(compute='_compute_field_visibility')
    hide_shunt_container_ids = fields.Boolean(compute='_compute_field_visibility')
    hide_shunt_to_id = fields.Boolean(compute='_compute_field_visibility')
    hide_tank_ids = fields.Boolean(compute='_compute_field_visibility')
    hide_tank_volume = fields.Boolean(compute='_compute_field_visibility')
    hide_liters_collected = fields.Boolean(compute='_compute_field_visibility')
    hide_liters_remaining = fields.Boolean(compute='_compute_field_visibility')
    hide_service_collection = fields.Boolean(compute='_compute_field_visibility')
    hide_tank = fields.Boolean(compute='_compute_field_visibility')
    hide_bin = fields.Boolean(compute='_compute_field_visibility')
    hide_hazardous_fields = fields.Boolean(compute='_compute_field_visibility')
    hide_general = fields.Boolean(compute='_compute_field_visibility')
    hide_none_general = fields.Boolean(compute='_compute_field_visibility')
    hide_service_placement = fields.Boolean(compute='_compute_field_visibility')
    hide_disposal_site = fields.Boolean(compute='_compute_hide_waste_type')
    hide_pickup_point = fields.Boolean(compute='_compute_hide_waste_type')

    @api.depends('service_requested_id','container_type_id', 'waste_type_id',
                 'service_requested_id.name','container_type_id.name','waste_type_id.name')
    def _compute_field_visibility(self):
        for rec in self:
            is_waste_type = (rec.service_requested_id.name or '').strip().lower()
            is_waste_details = (rec.service_requested_id.name or '').strip().lower()
            is_placement = (rec.service_requested_id.name or '').strip().lower()
            is_removal = (rec.service_requested_id.name or '').strip().lower()
            is_collection = (rec.service_requested_id.name or '').strip().lower()
            is_container = (rec.container_type_id.name or '').strip().lower()
            is_swap_lifted_bin = (rec.service_requested_id.name or '').strip().lower()
            is_swap_dropped_bin = (rec.service_requested_id.name or '').strip().lower()
            is_swap_dropped_to = (rec.service_requested_id.name or '').strip().lower()
            is_shunt_container_ids = (rec.service_requested_id.name or '').strip().lower()
            is_shunt_to_id = (rec.service_requested_id.name or '').strip().lower()
            is_tank_ids = (rec.container_type_id.name or '').strip().lower()
            is_tank_volume = (rec.container_type_id.name or '').strip().lower()
            is_litters_collected = (rec.container_type_id.name or '').strip().lower()
            is_letter_remaining = (rec.container_type_id.name or '').strip().lower()
            is_service_collection = (rec.service_requested_id.name or '').strip().lower()
            is_tank = (rec.container_type_id.name or '').strip().lower()
            is_bin = (rec.container_type_id.name or '').strip().lower()
            is_hazardous = (rec.waste_type_id.name or '').strip().lower()
            is_general = (rec.waste_type_id.name or '').strip().lower()
            is_none_general = (rec.waste_type_id.name or '').strip().lower()
            is_disposal_site = (rec.waste_type_id.name or '').strip().lower()
            is_service_placement = (rec.service_requested_id.name or '').strip().lower()
            is_pickup_point = (rec.service_requested_id.name or '').strip().lower()

            rec.hide_waste_type = (is_waste_type == 'placement of bins')
            rec.hide_waste_details = (is_waste_details == 'placement of bins')
            rec.hide_droppoff_container_ids_placement = (is_placement == 'placement of bins')
            rec.hide_droppoff_container_ids_removal = (is_removal == 'removal of bins')
            rec.hide_droppoff_container_ids_collection = (is_collection == 'waste collection & disposal')
            rec.hide_droppoff_container_ids_is_bin = (is_container == 'bin')
            rec.hide_lifted_bin_ids_swap = (is_swap_lifted_bin == 'swapping of bins')
            rec.hide_dropped_bin_ids_swap = (is_swap_dropped_bin == 'swapping of bins')
            rec.hide_dropped_to_swap = (is_swap_dropped_to == 'swapping of bins')
            rec.hide_shunt_container_ids = (is_shunt_container_ids == 'shunting of bins')
            rec.hide_shunt_to_id = (is_shunt_to_id == 'shunting of bins')
            rec.hide_tank_ids = (is_tank_ids == 'tank')
            rec.hide_tank_volume = (is_tank_volume == 'tank')
            rec.hide_liters_collected = (is_litters_collected == 'tank')
            rec.hide_liters_remaining = (is_letter_remaining == 'tank')
            rec.hide_service_collection = (is_service_collection == 'waste collection & disposal')
            rec.hide_tank = (is_tank == 'tank')
            rec.hide_bin = (is_bin == 'bin')
            rec.hide_hazardous_fields = (is_hazardous == 'hazardous')
            rec.hide_general = (is_general == 'general compactable')
            rec.hide_none_general = (is_none_general == 'general non compactable')
            rec.hide_disposal_site = (is_disposal_site == 'hazardous')
            rec.hide_service_placement = (is_service_placement == 'placement of bins')
            rec.hide_pickup_point = (is_pickup_point == 'placement of bins')

    # sale_order_id = fields.Many2one('sale.order', string="Sales Order")
    product_id = fields.Many2one('product.product', string="Product")
    # product_uom_qty = fields.Float(string="Quantity")
    price_unit = fields.Float(string="Unit Price")

    order_line_id = fields.Many2one(
        'sale.order.line',
        string="Sale Order Line",
        ondelete='set null',
        help="The sale order line that this service request should update."
    )

    # REPLACE your old product_uom_qty field with this one
    product_uom_qty = fields.Float(
        string="Quantity",
        compute="_compute_product_uom_qty",
        store=True,
        readonly=False,  # still editable if you want
    )


    @api.depends(
        "service_requested_id",
        "dropoff_container_ids",
        "shunt_container_ids",
        "lifted_bin_ids",
        "dropped_bin_ids",
    )
    def _compute_product_uom_qty(self):
        """
        Quantity follows selected bins and therefore increments/decrements automatically.
        """
        for rec in self:
            svc_code = (rec.service_requested_id.code or "").lower() \
                if rec.service_requested_id and hasattr(rec.service_requested_id, "code") \
                else (rec.service_requested_id.display_name or "").strip().lower()

            qty = 0.0

            if svc_code in ("placement of bins", "removal of bins", "waste collection & disposal"):
                qty = float(len(rec.dropoff_container_ids))

            elif svc_code == "shunting of bins":
                qty = float(len(rec.shunt_container_ids))

            elif svc_code == "swapping of bins":
                if rec.lifted_bin_ids:
                    qty = float(len(rec.lifted_bin_ids))
                elif rec.dropped_bin_ids:
                    qty = float(len(rec.dropped_bin_ids))
                else:
                    qty = 0.0

            rec.product_uom_qty = qty

    # ------------------------------------------------------------
    # SALE ORDER QTY SYNC
    # ------------------------------------------------------------
    def _sync_sale_order_qty(self):
        """
        Push current request qty to the related sale order line.
        Uses best matching line if order_line_id not set.
        """
        for rec in self:
            so = rec.sale_order_id
            if not so:
                continue

            qty = rec.product_uom_qty or 0.0

            # 1) Use explicitly linked line if present
            line = rec.order_line_id
            if line and line.order_id != so:
                line = False

            # 2) Try to find a line linked by custom field (if you later add one)
            if not line and 'waste_request_id' in so.order_line._fields:
                line = so.order_line.filtered(lambda l: l.waste_request_id.id == rec.id)[:1]

            # 3) Try to match by service_requested_id if line has that field
            if not line and rec.service_requested_id and 'service_requested_id' in so.order_line._fields:
                line = so.order_line.filtered(
                    lambda l: l.service_requested_id.id == rec.service_requested_id.id
                )[:1]

            # 4) Fallback: first order line (keeps system working even without config)
            if not line:
                line = so.order_line[:1]

            if line:
                # avoid recursion if you later add reverse sync
                line.with_context(skip_waste_sync=True).write({
                    'product_uom_qty': qty
                })
                rec.order_line_id = line

    @api.model_create_multi
    def create(self, vals_list):
        # Handle sequence for name (multi-create safe)
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'waste.service.request'
                ) or 'New'

        recs = super().create(vals_list)

        # Link driver + sale order to this service request
        for rec in recs:
            if rec.driver_id:
                rec.driver_id.service_request_id = rec.id
            if rec.sale_order_id:
                rec.sale_order_id.service_request_id = rec.id

        # Sync quantities to sale order after create
        recs._sync_sale_order_qty()

        return recs

    def write(self, vals):
        res = super().write(vals)

        # Keep driver + sale order links synced after updates
        for rec in self:
            if rec.driver_id:
                rec.driver_id.service_request_id = rec.id
            if rec.sale_order_id:
                rec.sale_order_id.service_request_id = rec.id

        # If bins/service/qty changed, recompute + sync to sale order
        if any(k in vals for k in [
            'product_uom_qty',
            'dropoff_container_ids',
            'shunt_container_ids',
            'lifted_bin_ids',
            'dropped_bin_ids',
            'service_requested_id',
        ]):
            self._sync_sale_order_qty()

        return res

    # @api.model_create_multi
    # def create(self, vals_list):
    #     recs = super().create(vals_list)
    #     recs._sync_sale_order_qty()
    #     return recs
    #
    # def write(self, vals):
    #
    #
    #     res = super().write(vals)
    #
    #     # if bins/service changed, qty recomputed -> sync to sale order
    #     if any(k in vals for k in [
    #         'product_uom_qty',
    #         'dropoff_container_ids',
    #         'shunt_container_ids',
    #         'lifted_bin_ids',
    #         'dropped_bin_ids',
    #         'service_requested_id',
    #     ]):
    #         self._sync_sale_order_qty()
    #
    #     return res

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        for rec in self:
            if not rec.sale_order_id or not rec.sale_order_id.order_line:
                continue

            line = rec.sale_order_id.order_line[0]  # or your own logic

            rec.product_id = line.product_id.id
            rec.product_uom_qty = line.product_uom_qty
            rec.price_unit = line.price_unit

            # Clear previous
            rec.update({
                'service_requested_id': False,
                'waste_type_id': False,
                'waste_details_id': False,
                'bin_type_id': False,
                'tank_volume_id': False,
                'container_type_id': False,
            })

            # Map product attribute name -> (your model, your field)
            attr_to_model_field = {
                'service requested': ('service.request', 'service_requested_id'),
                'waste type':        ('waste.type',        'waste_type_id'),
                'waste details':     ('waste.details',     'waste_details_id'),
                'bin type':          ('bin.type',          'bin_type_id'),
                'tank volume':       ('tank.volume',       'tank_volume_id'),
                'container type':    ('container.type',    'container_type_id'),
            }

            PAV = self.env['product.attribute.value']
            for ptav in line.product_id.product_template_attribute_value_ids:
                attr_name = (ptav.attribute_id.name or '').strip().lower()
                pav = ptav.product_attribute_value_id  # a product.attribute.value record
                if not pav:
                    continue

                model_field = attr_to_model_field.get(attr_name)
                if not model_field:
                    continue

                model_name, field_name = model_field

                # Find your config record that points to this exact PAV
                config_rec = self.env[model_name].search([('pav_id', '=', pav.id)], limit=1)
                if not config_rec:
                    # Fallback by name (optional)
                    config_rec = self.env[model_name].search([('name', '=', pav.name)], limit=1)

                if config_rec and not getattr(rec, field_name):
                    setattr(rec, field_name, config_rec.id)

        # ---------- Helpers ----------

    @api.depends('tank_ids.tank_volume_id')
    def _compute_tank_volume(self):
        for rec in self:
            rec.tank_volume_id = rec.tank_ids[:1].tank_volume_id or False

    @api.depends('liters_collected', 'tank_volume_id', 'tank_volume_id.name')
    def _compute_liters_remaining(self):
        for rec in self:
            capacity = 0.0

            tv = rec.tank_volume_id
            if tv:
                # 1) Prefer a proper numeric field if your model has one
                for fld in ('capacity_liters', 'liters', 'capacity', 'volume_l', 'volume'):
                    if fld in tv._fields:
                        val = getattr(tv, fld, 0.0) or 0.0
                        if val:
                            capacity = float(val)
                            break

                # 2) Fallback: parse from name (handles "5 000 L", "5,000L", "2.5 kL", "5000 litres")
                if not capacity:
                    label = (tv.display_name or '').strip().lower()
                    label = label.replace('litres', 'l').replace('liters', 'l')
                    m = re.search(r'(\d[\d\s,\.]*)\s*(k?l)\b', label)  # number + unit (l or kl)
                    if m:
                        num = m.group(1).replace(' ', '').replace(',', '')
                        unit = m.group(2)
                        try:
                            capacity = float(num)
                            if unit == 'kl':  # kiloliters → liters
                                capacity *= 1000.0
                        except ValueError:
                            capacity = 0.0
                    else:
                        # last fallback: first number anywhere
                        m2 = re.search(r'\d[\d\s,\.]*', label)
                        if m2:
                            num = m2.group(0).replace(' ', '').replace(',', '')
                            try:
                                capacity = float(num)
                            except ValueError:
                                capacity = 0.0

            rec.liters_remaining = max(0.0, (capacity or 0.0) - (rec.liters_collected or 0.0))

    # ---------- State actions ----------
    def action_draft(self):
        self.write({'state': 'draft'})

    def action_generated(self):
        for rec in self:
            # Decide which containers to mark as in use for "generated"
            targets = self.env['waste.container']
            # If your logic actually depends on service type, put that logic here.
            targets |= rec.dropoff_container_ids
            targets |= rec.lifted_bin_ids | rec.dropped_bin_ids
            targets |= rec.shunt_container_ids
            targets |= rec.tank_ids

            # Update in bulk. If you don't have inUse, remove it and keep status only.
            vals = {}
            if 'inUse' in targets._fields:
                vals['inUse'] = True
            if 'status' in targets._fields:
                vals['status'] = 'in_use'
            if vals:
                targets.write(vals)

            rec.state = 'generated'

    # def action_set_scheduled(self):
    #     """
    #     Manually move to 'scheduled'.
    #     Only change state, do NOT touch any other fields.
    #
    #     """
    #     self.state = 'scheduled'
    #
    #     template = self.env.ref(
    #         'waste_management_zakheni.mail_tmpl_service_request_driver_invitation',
    #         raise_if_not_found=False,
    #     )
    #     if template:
    #         template.send_mail(self.id, force_send=True)

    def action_set_scheduled(self):
        """
        Manually move to 'scheduled'.
        Only change state, then send email based on is_service_provider.
        """
        for rec in self:
            rec.state = "scheduled"

            if rec.is_service_provider:
                # send SERVICE PROVIDER template
                template = rec.env.ref(
                    "waste_management_zakheni.mail_tmpl_service_request_service_provide_invitation",
                    raise_if_not_found=False,
                )
            else:
                # send DRIVER template
                template = rec.env.ref(
                    "waste_management_zakheni.mail_tmpl_service_request_driver_invitation",
                    raise_if_not_found=False,
                )

            if template:
                template.send_mail(rec.id, force_send=True)

        return True

    def action_mark_done(self):
        for record in self:
            svc_code = (record.service_requested_id.code or '').lower() \
                if record.service_requested_id and hasattr(record.service_requested_id, 'code') \
                else (record.service_requested_id.display_name or '').strip().lower()

            dest_pps = record.pickup_point_ids
            dest_pp_ids = dest_pps.ids
            dest_pp_label = ", ".join(dest_pps.mapped("display_name")) if dest_pps else "Unknown"

            cust = record.customer_id or record.partner_id

            # -------------------------
            # YOUR EXISTING LOGIC
            # -------------------------
            if svc_code == 'removal of bins':
                for container in record.dropoff_container_ids:
                    if 'pickup_point_ids' in container._fields:
                        container.pickup_point_ids = [(5, 0, 0)]
                    if 'pickup_point_id' in container._fields:
                        container.pickup_point_id = False
                    if 'customer_id' in container._fields:
                        container.customer_id = False
                    if 'status' in container._fields:
                        container.status = 'un_use'
                    record.message_post(body=f"Removed bin: {container.display_name}")

            elif svc_code == 'swapping of bins':
                for lifted_bin in record.lifted_bin_ids:
                    from_label = ", ".join(lifted_bin.pickup_point_ids.mapped("display_name")) \
                        if 'pickup_point_ids' in lifted_bin._fields and lifted_bin.pickup_point_ids else "Unknown"

                    if 'pickup_point_ids' in lifted_bin._fields:
                        lifted_bin.pickup_point_ids = [(5, 0, 0)]
                    if 'pickup_point_id' in lifted_bin._fields:
                        lifted_bin.pickup_point_id = False
                    if 'customer_id' in lifted_bin._fields:
                        lifted_bin.customer_id = False
                    if 'status' in lifted_bin._fields:
                        lifted_bin.status = 'un_use'

                    record.message_post(
                        body=f"Lifted bin '{lifted_bin.display_name}' from '{from_label}'"
                    )

                for dropped_bin in record.dropped_bin_ids:
                    if 'pickup_point_ids' in dropped_bin._fields:
                        dropped_bin.pickup_point_ids = [(6, 0, dest_pp_ids)]
                    if 'pickup_point_id' in dropped_bin._fields and dest_pps:
                        dropped_bin.pickup_point_id = dest_pps[0]
                    if 'customer_id' in dropped_bin._fields and cust:
                        dropped_bin.customer_id = cust
                    if 'status' in dropped_bin._fields:
                        dropped_bin.status = 'in_use'

                    record.message_post(
                        body=f"Dropped bin '{dropped_bin.display_name}' at '{dest_pp_label}'"
                    )

            elif svc_code == 'shunting of bins':
                from_label = record.shunt_from_id.display_name if record.shunt_from_id else "Unknown"
                to_label = record.shunt_to_id.display_name if record.shunt_to_id else "Unknown"

                for bin_rec in record.shunt_container_ids:
                    if 'pickup_point_id' in bin_rec._fields:
                        bin_rec.pickup_point_id = record.shunt_to_id
                    if 'pickup_point_ids' in bin_rec._fields and record.shunt_to_id:
                        bin_rec.pickup_point_ids = [(4, record.shunt_to_id.id)]
                    if 'customer_id' in bin_rec._fields and cust:
                        bin_rec.customer_id = cust
                    if 'status' in bin_rec._fields:
                        bin_rec.status = 'in_use'

                    record.message_post(
                        body=f"Shunted bin '{bin_rec.display_name}' from '{from_label}' to '{to_label}'"
                    )

            elif svc_code == 'placement of bins':
                for container in record.dropoff_container_ids:
                    if 'pickup_point_id' in container._fields and container.pickup_point_id:
                        dest_pp_single = container.pickup_point_id
                    elif dest_pps:
                        dest_pp_single = dest_pps[0]
                    else:
                        dest_pp_single = False

                    label = dest_pp_single.display_name if dest_pp_single else dest_pp_label

                    if 'pickup_point_id' in container._fields and dest_pp_single:
                        container.pickup_point_id = dest_pp_single
                    if 'pickup_point_ids' in container._fields and dest_pp_single:
                        container.pickup_point_ids = [(4, dest_pp_single.id)]
                    if 'customer_id' in container._fields and cust:
                        container.customer_id = cust
                    if 'status' in container._fields:
                        container.status = 'in_use'

                    record.message_post(
                        body=f"Placed bin: {container.display_name} at {label}"
                    )

            elif svc_code == 'waste collection & disposal':
                for container in record.dropoff_container_ids:
                    if 'pickup_point_ids' in container._fields:
                        container.pickup_point_ids = [(5, 0, 0)]
                    if 'pickup_point_id' in container._fields:
                        container.pickup_point_id = False
                    if 'customer_id' in container._fields:
                        container.customer_id = False
                    if 'status' in container._fields:
                        container.status = 'un_use'

                    record.message_post(
                        body=f"Collected & Disposed bin: {container.display_name}"
                    )

            # tanks logic unchanged...
            for tank in record.tank_ids:
                if 'pickup_point_ids' in tank._fields:
                    tank.pickup_point_ids = [(6, 0, dest_pp_ids)]
                if 'pickup_point_id' in tank._fields and dest_pps:
                    tank.pickup_point_id = dest_pps[0]
                if 'customer_id' in tank._fields and cust:
                    tank.customer_id = cust
                if 'status' in tank._fields:
                    tank.status = 'un_use'

                record.message_post(
                    body=f"Collected & Emptied tank: {tank.display_name} "
                         f"({tank.tank_volume_id.display_name or ''})"
                )

                # ✅ AUDIT LOG - one line grouped exactly like requested
                audit_summary = record._get_pickup_point_bins_summary_string(limit_per_point=None)
                if audit_summary:
                    record.message_post(
                        body=_("Bins per Pickup/Dropoff Point: %s") % audit_summary
                    )

            record.state = "done"


    work_sheet_id = fields.Many2one(
        "waste.worksheet",
        string="Work Sheet",
        ondelete="set null"
    )

    def action_cancelled(self):
        self.ensure_one()
        # 1) Update worksheet state (adjust target state as you prefer)
        if self.work_sheet_id and self.work_sheet_id.state in ('draft', 'in_progress', 'done'):
            # Example: move worksheet back to draft when request is cancelled
            self.work_sheet_id.with_context(skip_auto_state=True).write({
                'state': 'in_progress',
            })

        return {
                'type': 'ir.actions.act_window',
                'name': 'Enter Reject Reason',
                'res_model': 'reject.service.request.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_user_id': self.id,
                },
            }

    def action_amend(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Enter Amend Comment',
            'res_model': 'amend.service.request.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
            },
        }



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
            "target": "current",
            "domain": [("service_request_id", "=", self.id)],
            "context": {"default_service_request_id": self.id},
        }

    extra_product_line_ids = fields.One2many(
        'waste.service.request.extra.line',
        'request_id',
        string='Extra Products',
    )

    extra_product_count = fields.Integer(
        compute="_compute_extra_product_count",
        string="Extra Products",
    )

    @api.depends('extra_product_line_ids')
    def _compute_extra_product_count(self):
        for rec in self:
            rec.extra_product_count = len(rec.extra_product_line_ids)

    def action_open_product_selector(self):
        """Smart button → fancy product grid (kanban)"""
        self.ensure_one()
        action = self.env.ref(
            'waste_management_zakheni.action_waste_request_product_selector'
        ).read()[0]

        ctx = dict(self.env.context)
        ctx.update({
            'waste_request_id': self.id,
            'search_default_sale_ok': 1,  # only storable/service for sale
        })
        action['context'] = ctx
        return action

    def action_push_extra_products_to_so(self):
        """Create / update sale.order.line from extra products."""
        for req in self:
            if not req.sale_order_id:
                raise UserError(_('No Sales Order linked to this request.'))
            so = req.sale_order_id

            for line in req.extra_product_line_ids:
                if line.sale_order_line_id:
                    # update existing SO line
                    line.sale_order_line_id.write({
                        'product_uom_qty': line.quantity,
                        'price_unit': line.price_unit,
                    })
                else:
                    # create new SO line
                    sol_vals = {
                        'order_id': so.id,
                        'product_id': line.product_id.id,
                        'name': line.product_id.get_product_multiline_description_sale()
                                or line.product_id.display_name,
                        'product_uom_qty': line.quantity,
                        'price_unit': line.price_unit,
                    }
                    sol = self.env['sale.order.line'].create(sol_vals)
                    line.sale_order_line_id = sol.id
        return True

    wizard_pickup_point_ids = fields.Many2many(
        'pickup.point',
        'waste_request_wizard_pickup_rel',
        'request_id',
        'pickup_point_id',
        string="Pickup/Dropoff Points",
        help="Pickup/Dropoff points captured from Assign Bins wizard.",
    )

    pickup_point_bins_summary = fields.Text(
        string="Pickup/Dropoff Points & Bins Summary",
        compute="_compute_pickup_point_bins_summary",
        store=False,
    )

    @api.depends(
        "bin_line_ids.pickup_point_id",
        "bin_line_ids.container_ids",
        "bin_line_ids.shunt_container_ids",
        "bin_line_ids.lifted_container_ids",
        "bin_line_ids.dropped_container_ids",
    )
    def _compute_pickup_point_bins_summary(self):
        for rec in self:
            parts = []

            # use saved lines (persistent)
            for line in rec.bin_line_ids:
                pp = line.pickup_point_id
                if not pp:
                    continue

                # decide which bins to show per service
                svc_code = (rec.service_requested_id.code or "").lower() \
                    if rec.service_requested_id and hasattr(rec.service_requested_id, "code") \
                    else (rec.service_requested_id.display_name or "").strip().lower()

                if svc_code == "shunting of bins":
                    bins = line.shunt_container_ids
                elif svc_code == "swapping of bins":
                    # show both in one line
                    lifted = ", ".join(b.display_name for b in line.lifted_container_ids)
                    dropped = ", ".join(b.display_name for b in line.dropped_container_ids)
                    text = f"{pp.display_name} [Lifted: {lifted or '-'} | Dropped: {dropped or '-'}]"
                    parts.append(text)
                    continue
                else:
                    bins = line.container_ids

                bin_names = [b.display_name for b in bins]
                if len(bin_names) > 3:
                    shown = ", ".join(bin_names[:3]) + ", ..."
                else:
                    shown = ", ".join(bin_names)

                parts.append(f"{pp.display_name} [{shown}]")

            rec.pickup_point_bins_summary = ", ".join(parts) if parts else ""

    # ---------------------------------------------------------
    # Smart button count = number of bins currently selected
    # ---------------------------------------------------------

    wizard_pickup_point_count = fields.Integer(
        compute="_compute_wizard_pickup_point_count",
        store=False,
    )

    @api.depends('wizard_pickup_point_ids')
    def _compute_wizard_pickup_point_count(self):
        for rec in self:
            rec.wizard_pickup_point_count = len(rec.wizard_pickup_point_ids)

    bin_line_ids = fields.One2many(
        "waste.request.bin.line",
        "request_id",
        string="Pickup/Bins Lines",
    )

    bin_line_count = fields.Integer(
        compute="_compute_bin_line_count",
        store=False,
    )

    @api.depends('bin_line_ids')
    def _compute_bin_line_count(self):
        for rec in self:
            rec.bin_line_count = len(rec.bin_line_ids)

    @api.depends('dropoff_container_ids', 'shunt_container_ids',
                 'lifted_bin_ids', 'dropped_bin_ids')
    def _compute_bin_line_count(self):
        for rec in self:
            svc_code = (rec.service_requested_id.code or '').lower() \
                if rec.service_requested_id and hasattr(rec.service_requested_id, 'code') \
                else (rec.service_requested_id.display_name or '').strip().lower()

            if svc_code in ('placement of bins', 'removal of bins', 'waste collection & disposal'):
                rec.bin_line_count = len(rec.dropoff_container_ids)
            elif svc_code == 'shunting of bins':
                rec.bin_line_count = len(rec.shunt_container_ids)
            elif svc_code == 'swapping of bins':
                rec.bin_line_count = len(rec.lifted_bin_ids) + len(rec.dropped_bin_ids)
            else:
                rec.bin_line_count = 0

    # ---------------------------------------------------------
    # Open wizard from smart button
    # ---------------------------------------------------------
    def action_open_bin_assignment_wizard(self):
        self.ensure_one()
        action = self.env.ref('waste_management_zakheni.action_waste_assign_bin_wizard').read()[0]
        action['context'] = {
            'default_request_id': self.id,
            'active_id': self.id,
            'active_model': self._name,
        }
        return action

    sale_order_count = fields.Integer(
        string="Sale Order Count",
        compute="_compute_sale_order_count"
    )

    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = 1 if rec.sale_order_id else 0

    def action_open_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_("No Sales Order linked to this Waste Request."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Sales Order"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_order_id.id,
            "target": "current",
        }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    service_request_id = fields.Many2one(
        'waste.service.request',
        string="Manifest",
        ondelete="set null"

    )
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)
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

    )

    # pickup_point_ids = fields.One2many(
    #     'pickup.point', 'sale_order_id',
    #     string="Drop-off/Pickup Point",
    #     domain="[('partner_id', '=', partner_id)]",
    #     required=True
    # )

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