from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError

class WasteWorksheet(models.Model):
    _name = "waste.worksheet"
    _description = "Waste Worksheet"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Request ID',
        required=True,
        # copy=False,
        readonly=True,
        default='New')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('waste.worksheet') or 'New'

        return super().create(vals)

    service_request_id = fields.Many2one(
        "waste.service.request",
        string="Service Request",
        ondelete="set null"
    )
    # Delivery information
    arrival_time = fields.Datetime(string='Arrival Date')
    return_date = fields.Datetime(string='Return Date')
    unit_of_measure = fields.Many2one('uom.uom', string='Units of Measure')
    kilometers = fields.Integer(string='Kilometers')
    quantity_collected = fields.Float(string='Quantity Collected')
    driver_signature = fields.Binary(string="Driver Signature", )
    service_provider_signature = fields.Binary(string="Service Provider Signature", )
    planned_date = fields.Datetime(string='Planned Date', related='service_request_id.planned_date', store=True)

    partner_id = fields.Many2one('res.partner', string="Customer", related='service_request_id.partner_id')
    pickup_point_id = fields.Many2one('pickup.point', string="Drop-off/Pickup Point",
                                      related='service_request_id.pickup_point_id')

    manifest_document = fields.Binary("Manifests Document", attachment=True)
    manifest_document_filename = fields.Char()

    weighbridge_slip = fields.Binary("Weighbridge Slip", attachment=True)
    weighbridge_slip_filename = fields.Char()

    safety_certificate = fields.Binary("Safety Certificate", attachment=True)
    safety_certificate_filename = fields.Char()

    # =========================
    # Date consistency checks
    # =========================
    @api.constrains('arrival_time', 'return_date', 'planned_date')
    def _check_dates(self):
        for rec in self:
            # 1) Arrival must not be before the planned date
            if rec.planned_date and rec.arrival_time and rec.arrival_time > rec.planned_date:
                raise ValidationError(_(
                    "Arrival Date/Time (%s) cannot be greater than the Planned Date (%s)."
                ) % (rec.arrival_time, rec.planned_date))

            # 2) Return must not be before arrival
            if rec.return_date and rec.arrival_time and rec.return_date < rec.arrival_time:
                raise ValidationError(_(
                    "Return Date/Time (%s) cannot be earlier than the Arrival Date/Time (%s)."
                ) % (rec.return_date, rec.arrival_time))

            # (Optional but usually logical)
            # Return must also not be before the planned date
            if rec.return_date and rec.planned_date and rec.return_date > rec.planned_date:
                raise ValidationError(_(
                    "Return Date/Time (%s) cannot be greater than the Planned Date (%s)."
                ) % (rec.return_date, rec.planned_date))

    def action_open_manifest_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Manifest Document',
            'res_model': 'waste.worksheet',
            'view_mode': 'form',
            'view_id': self.env.ref('waste_management_zakheni.view_manifest_document_up_pop').id,
            'res_id': self.id,
            'target': 'new',
        }

    def action_open_weighbridge_slip(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Weighbridge Slip',
            'res_model': 'waste.worksheet',
            'view_mode': 'form',
            'view_id': self.env.ref('waste_management_zakheni.view_weighbridge_slip_up_pop').id,
            'res_id': self.id,
            'target': 'new',
        }

    def action_open_safety_certificate(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Safety Certificate',
            'res_model': 'waste.worksheet',
            'view_mode': 'form',
            'view_id': self.env.ref('waste_management_zakheni.view_safety_certificate_up_pop').id,
            'res_id': self.id,
            'target': 'new',
        }

    service_requested_id = fields.Many2one('service.request', related='service_request_id.service_requested_id', string="Service Requested")
    waste_type_id = fields.Many2one('waste.type',related='service_request_id.waste_type_id', string="Waste Type")
    waste_details_id = fields.Many2one('waste.details',related='service_request_id.waste_details_id', string="Waste Details")
    bin_type_id = fields.Many2one('bin.type',related='service_request_id.bin_type_id', string="Bin Type")
    tank_volume_id = fields.Many2one('tank.volume',related='service_request_id.tank_volume_id', string="Tank Volume")
    container_type_id = fields.Many2one('container.type',related='service_request_id.container_type_id', string="Container type")
    pickup_point_ids = fields.Many2many(
        'pickup.point',
        'waste_worksheet_pickup_rel',  # <-- NEW table name
        'worksheet_id',  # <-- FK to waste.worksheet
        'pickup_point_id',  # FK to pickup.point (can stay same)
        string="Pickup Points",
    )
    liters_collected = fields.Float(string="Liters Collected", related='service_request_id.liters_collected', )
    liters_remaining = fields.Float(string="Liters Remaining",  related='service_request_id.liters_remaining', )
    product_id = fields.Many2one('product.product', string="Product",  related='service_request_id.product_id',)
    product_uom_qty = fields.Float(string="Quantity",  related='service_request_id.product_uom_qty',)
    price_unit = fields.Float(string="Unit Price",  related='service_request_id.price_unit',)



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

    @api.depends('service_requested_id', 'container_type_id', 'waste_type_id',
                 'service_requested_id.name', 'container_type_id.name', 'waste_type_id.name')
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


    inUse = fields.Boolean(string='InUse', related='service_request_id.inUse', defauld=True, )
    tank_ids = fields.Many2many('waste.container', 'waste_service_request_tanks_rel', string="Tanks",
                                related='service_request_id.tank_ids')
    # Shunt
    shunt_from_id = fields.Many2one('pickup.point', string="From Location", domain="[('partner_id', '=', partner_id)]",
                                    related='service_request_id.shunt_from_id')
    shunt_to_id = fields.Many2one('pickup.point', string="To Location", domain="[('partner_id', '=', partner_id)]",
                                  related='service_request_id.shunt_to_id')

    lifted_bin_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_lifted_rel',  # Different relation table
        'request_id',
        'container_id',
        string="Lifted Bins", related='service_request_id.lifted_bin_ids'
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
        ("in_progress", "In Progress"),
        ("done", "Done"),
    ], string="Status", default="draft", tracking=True)

    # ----------------------
    # Button Actions
    # ----------------------
    def action_set_to_draft(self):
        self.state = "draft"
        # for rec in self:
        #     rec.state = "draft"
        #     if rec.service_request_id:
        #         rec.service_request_id.state = "draft"

        # ---------- Button: start worksheet / dispatch truck ----------

    def action_start(self):
        for rec in self:
            # Update worksheet state
            rec.state = 'in_progress'

            # Update related service request to Dispatched
            if rec.service_request_id and rec.service_request_id.state in ('scheduled', 'assigned', 'generated'):
                rec.service_request_id.with_context(skip_auto_state=True).write({
                    'state': 'dispatched'
                })

    def action_done(self):
        for rec in self:
            # Mark worksheet done
            rec.state = 'done'

            # Update related Service Request state to Service Delivered
            if rec.service_request_id and rec.service_request_id.state in ('scheduled', 'assigned', 'generated',
                                                                               'dispatched', 'cancelled'):
                rec.service_request_id.with_context(skip_auto_state=True).write({
                    'state': 'service_delivered'
                })
    #
    # def action_set_to_done(self):
    #     self.state = "done"
    #     # for rec in self:
    #     #     rec.state = "delivered"
    #     #     if rec.service_request_id:
    #     #         rec.service_request_id.state = "delivered"

    image_ids = fields.One2many(
        'waste.worksheet.image',
        'worksheet_id',
        string='Photos',
    )

    notes_html = fields.Html(
        string="Worksheet Notes",
        help="Add notes and embed pictures directly in the content.",
    )


class WasteWorksheetImage(models.Model):
    _name = 'waste.worksheet.image'
    _description = 'Waste Worksheet Image'

    worksheet_id = fields.Many2one(
        'waste.worksheet',
        string='Worksheet',
        ondelete='cascade',
        required=True,
    )

    name = fields.Char(string='Description')
    image = fields.Image(
        string='Image',
        max_width=1920,
        max_height=1920,
        attachment=True,
    )
