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
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )


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

    # driver_id = fields.Many2one('hr.employee')
    # driver_email = fields.Char(string="Driver Email", related="driver_id.work_email")
    driver_id = fields.Many2one("hr.employee", string="Driver", )
    driver_work_email = fields.Char(string="Driver Work email", related="driver_id.work_email", store=True)

    manifest_document = fields.Binary("Manifests Document", attachment=True)
    manifest_document_filename = fields.Char()

    weighbridge_slip = fields.Binary("Weighbridge Slip", attachment=True)
    weighbridge_slip_filename = fields.Char()

    safety_certificate = fields.Binary("Safety Certificate", attachment=True)
    safety_certificate_filename = fields.Char()

    # Prevent duplicate of service_request_id
    _sql_constraints = [
        (
            'waste_worksheet_request_uniq',
            'unique(service_request_id)',
            'This Service Request already has a worksheet.'
        ),
    ]

    @api.constrains('service_request_id')
    def _check_unique_service_request(self):
        """Extra safety at ORM level (nice error during imports)."""
        for rec in self:
            if not rec.service_request_id:
                continue
            dup = self.search([
                ('id', '!=', rec.id),
                ('service_request_id', '=', rec.service_request_id.id),
            ], limit=1)
            if dup:
                raise ValidationError(_(
                    "A worksheet already exists for service request %s."
                ) % rec.service_request_id.display_name)
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
            # # Return must also not be before the planned date
            # if rec.return_date and rec.planned_date and rec.return_date > rec.planned_date:
            #     raise ValidationError(_(
            #         "Return Date/Time (%s) cannot be greater than the Planned Date (%s)."
            #     ) % (rec.return_date, rec.planned_date))

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

    billing_kl = fields.Float(
        related='service_request_id.billing_kl',
        string="Billing kL",
        store=True,
        readonly=True,
        help="Kiloliters used for billing (from Service Request)."
    )

    billing_amount = fields.Float(
        related='service_request_id.billing_amount',
        string="Billing Amount (Excl. VAT)",
        store=True,
        readonly=True,
        help="Calculated billing amount (from Service Request)."
    )

    qty_updated_from_worksheet = fields.Boolean(
        related='service_request_id.qty_updated_from_worksheet',
        string="Qty Updated From Worksheet",
        store=True,
        readonly=True,
    )

    truck_tanker_id = fields.Many2one('tank.volume', string="Track Tanker", related="service_request_id.tank_volume_id", store=False)

    service_requested_id = fields.Many2one('service.request', related='service_request_id.service_requested_id', string="Service Requested")
    waste_type_id = fields.Many2one('waste.type',related='service_request_id.waste_type_id', string="Waste Type")
    waste_details_id = fields.Many2one('waste.details',related='service_request_id.waste_details_id', string="Waste Details")
    bin_type_id = fields.Many2one('bin.type',related='service_request_id.bin_type_id', string="Bin Type")
    tank_volume_id = fields.Many2one('tank.volume',related='service_request_id.tank_volume_id', string="Tank Volume")
    container_type_id = fields.Many2one('container.type',related='service_request_id.container_type_id', string="Container type")
    # pickup_point_ids = fields.Many2many(
    #     'pickup.point',
    #     'waste_worksheet_pickup_rel',  # <-- NEW table name
    #     'worksheet_id',  # <-- FK to waste.worksheet
    #     'pickup_point_id',  # FK to pickup.point (can stay same)
    #     string="Pickup Points",
    # )
    liters_collected = fields.Float(string="Liters Collected", related='service_request_id.liters_collected', )
    # liters_remaining = fields.Float(string="Liters Remaining",  related='service_request_id.liters_remaining', )
    # product_id = fields.Many2one('product.product', string="Product",  related='service_request_id.product_id',)
    # product_uom_qty = fields.Float(string="Quantity",  related='service_request_id.product_uom_qty',)
    # price_unit = fields.Float(string="Unit Price",  related='service_request_id.price_unit',)
    sale_order_id = fields.Many2one('sale.order', string="Sales Order")

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


    inUse = fields.Boolean(string='InUse', related='service_request_id.inUse' )
    tank_ids = fields.Many2many('waste.container', 'waste_service_request_tanks_rel', string="Tanks",
                                related='service_request_id.tank_ids')

    #NEW
    pickup_point_ids = fields.Many2many(
        'pickup.point',
        'waste_request_pickup_point_rel',
        'request_id',
        'pickup_point_id',
        string="Pickup Points",
        related='service_request_id.pickup_point_ids'
    )

    dropoff_point_ids = fields.Many2many(
        'pickup.point',
        'waste_request_dropoff_point_rel',
        'request_id',
        'pickup_point_id',
        string="Drop-off Points",
        related='service_request_id.dropoff_point_ids'
    )
    bin_lifted_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_bin_lifted_rel',  # relation table
        'request_id',  # FK to waste.service.request
        'waste_container_id',  # FK to waste.container (existing column)
        string="Bin Lifted",
        related='service_request_id.bin_lifted_ids'
    )

    bin_dropped_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_bin_dropped_rel',  # relation table
        'request_drop_id',  # FK to waste.service.request
        'waste_container_id',  # FK to waste.container (existing column)
        string="Bin Dropped",
        related='service_request_id.bin_dropped_ids'
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
            template = self.env.ref(
                'waste_management_zakheni.mail_tmpl_service_request_worksheet_completion',
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(self.id, force_send=True)

    image_ids = fields.One2many(
        'waste.worksheet.image',
        'worksheet_id',
        string='Photos',
    )

    notes_html = fields.Html(
        string="Worksheet Notes",
        help="Add notes and embed pictures directly in the content.",
    )

    pickup_point_bins_summary = fields.Text(
        related="service_request_id.pickup_point_bins_summary",
        string="Pickup/Dropoff Points & Bins Summary",
        store=True,
        readonly=True,
    )

    wizard_pickup_point_count = fields.Integer(
        related="service_request_id.wizard_pickup_point_count",
        store=False,
    )

    bin_line_ids = fields.One2many(
        "waste.request.bin.line",
        "request_id",
        string="Pickup/Bins Lines",
        related="service_request_id.bin_line_ids",
    )
    bin_line_count = fields.Integer(
        related="service_request_id.bin_line_count",
        store=False,
    )

    sale_order_count = fields.Integer(
        string="Sale Order Count",
        related="service_request_id.sale_order_count",
    )


    # REPLACE your old product_uom_qty field with this one
    product_uom_qty = fields.Float(
        related="service_request_id.product_uom_qty",
        string="Quantity",
        store=True,
        readonly=False,# still editable if you want
    )
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

    order_line_id = fields.Many2one(
        'sale.order.line',
        string="Sale Order Line",
        ondelete='set null',
        help="The sale order line that this service request should update."
    )

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
                    'waste.worksheet'
                ) or 'New'


        recs = super().create(vals_list)

        for ws in recs:
            if ws.service_request_id and not ws.service_request_id.work_sheet_id:
                ws.service_request_id.work_sheet_id = ws.id
            elif ws.service_request_id:
                # If you always want the *latest* worksheet, uncomment this:
                # ws.service_request_id.work_sheet_id = ws.id
                pass

        # Sync quantities to sale order after create
        recs._sync_sale_order_qty()

        return recs

    def write(self, vals):
        # We want the context 'from_worksheet' when product_uom_qty is written
        # so that WasteServiceRequest.write can know where the change came from.
        ws = self.with_context(from_worksheet=True)
        res = super(WasteWorksheet, ws).write(vals)

        # If you removed worksheet SO sync, you can delete the block below.
        # If you kept it and still want it, you can leave this:
        if any(k in vals for k in [
            'product_uom_qty',
            'service_requested_id',
            'bin_lifted_ids',
            'bin_dropped_ids',
        ]):
            self._sync_sale_order_qty()

        return res

    # def write(self, vals):
    #     res = super().write(vals)
    #     #
    #     # # if bins/service/qty changed, recompute -> sync to sale order
    #     if any(k in vals for k in [
    #         'product_uom_qty',
    #         'service_requested_id',
    #         'bin_lifted_ids',
    #         'bin_dropped_ids',
    #     ]):
    #         self._sync_sale_order_qty()
    #
    #     return res


    def action_open_ws_bin_assignment_wizard(self):
        self.ensure_one()
        # ✅ Reuse the existing wizard action
        action = self.env.ref("waste_management_zakheni.action_waste_assign_bin_wizard").read()[0]

        ctx = dict(self.env.context)
        ctx.update({
            "default_request_id": self.service_request_id.id,
            "active_id": self.service_request_id.id,
            "active_model": "waste.service.request",
        })
        action["context"] = ctx
        return action

    def action_open_waste_request(self):
        self.ensure_one()
        if not self.service_request_id:
            return False

        return {
            "type": "ir.actions.act_window",
            "name": _("Waste Request"),
            "res_model": "waste.service.request",
            "view_mode": "form",
            "res_id": self.service_request_id.id,
            "target": "current",
        }

    request_sale_order_id = fields.Many2one('sale.order', related="service_request_id.sale_order_id", String="Sale Order")

    def action_open_sale_order(self):
        self.ensure_one()
        if not self.request_sale_order_id:
            return False

        return {
            "type": "ir.actions.act_window",
            "name": _("Sales  Order"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.request_sale_order_id.id,
            "target": "current",
        }

class WasteWorksheetBinLine(models.Model):
    _name = "waste.worksheet.bin.line"
    _description = "Waste Worksheet Bin Line"

    worksheet_id = fields.Many2one(
        "waste.worksheet",
        required=True,
        ondelete="cascade",
    )

    waste_request_bin_id = fields.Many2one(
        "waste.request.bin.line",
        string="Service Request",
        required=True,
        ondelete="cascade",
        index=True,
    )

    request_id = fields.Many2one(
        "waste.service.request",
        string="Service Request",
        required=True,
        ondelete="cascade",
        index=True,
    )

    pickup_point_id = fields.Many2one(
        "pickup.point",
        string="Pickup Point",
        required=True,
    )

    dropoff_point_id = fields.Many2one(
        "pickup.point",
        string="Drop-off Point",
    )

    bin_lifted_ids = fields.Many2many(
        "waste.container",
        "waste_ws_request_bin_line_lifted_rel",
        "line_id",
        "container_id",
        string="Bin Lifted",
    )

    bin_dropped_ids = fields.Many2many(
        "waste.container",
        "waste_ws_request_bin_line_dropped_rel",
        "line_id",
        "container_id",
        string="Bin Dropped",
    )

    tank_ids = fields.Many2many(
        "waste.container",
        "waste_ws_request_tank_line_collect_rel",
        "line_id",
        "container_id",
        string="Tank",
    )

    liters_collected = fields.Float(string="Liters Collected")
    # liters_remaining = fields.Float(string="Liters Remaining")


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
