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
    # product_uom_qty = fields.Float(string="Quantity",  related='service_request_id.product_uom_qty',)
    price_unit = fields.Float(string="Unit Price",  related='service_request_id.price_unit',)
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
            template = self.env.ref(
                'waste_management_zakheni.mail_tmpl_service_request_worksheet_completion',
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(self.id, force_send=True)
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

    # wizard_pickup_point_ids = fields.Many2many(
    #     'pickup.point',
    #     'waste_request_wizard_pickup_rel',
    #     'request_id',
    #     'pickup_point_id',
    #     related="service_request_id.wizard_pickup_point_ids",
    #     string="Pickup/Dropoff Points",
    #     help="Pickup/Dropoff points captured from Assign Bins wizard.",
    #     store=True,
    # )

    wizard_pickup_point_ids = fields.Many2many(
        related="service_request_id.wizard_pickup_point_ids",
        string="Pickup/Dropoff Points",
        readonly=True,
        store=False,  # set True only if you need searching/grouping
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
        related="service_request_id.bin_line_ids",
        string="Pickup/Bins Lines",
    )

    bin_line_count = fields.Integer(
        compute="_compute_bin_line_count",
        store=True,
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
                    'waste.worksheet'
                ) or 'New'

        recs = super().create(vals_list)

        # Sync quantities to sale order after create
        recs._sync_sale_order_qty()

        return recs

    def write(self, vals):
        res = super().write(vals)

        # if bins/service/qty changed, recompute -> sync to sale order
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
    def action_open_ws_bin_assignment_wizard(self):
        self.ensure_one()
        action = self.env.ref("waste_management_zakheni.action_ws_assign_bin_wizard").read()[0]
        action["context"] = {
            "active_id": self.id,
            "active_model": self._name,
        }
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

    pickup_point_id = fields.Many2one(
        "pickup.point",
        string="Pickup / Dropoff Point",
        related="waste_request_bin_id.pickup_point_id",

    )

    # Placement / Removal / Collection
    container_ids = fields.Many2many(
        related="waste_request_bin_id.container_ids",
        string="Containers",
        readonly=True,
        store=False,
    )

    # Shunting
    shunt_container_ids = fields.Many2many(
        related="waste_request_bin_id.shunt_container_ids",
        string="Bins to Shunt",
        readonly=True,
        store=False,
    )

    # Swapping
    lifted_container_ids = fields.Many2many(
        related="waste_request_bin_id.lifted_container_ids",
        string="Lifted Bins",
        readonly=True,
        store=False,
    )
    dropped_container_ids = fields.Many2many(
        related="waste_request_bin_id.dropped_container_ids",
        string="Dropped Bins",
        readonly=True,
        store=False,
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
