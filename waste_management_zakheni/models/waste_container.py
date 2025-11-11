from odoo import models, fields, api
from odoo.exceptions import UserError


class WasteContainer(models.Model):
    _name = 'waste.container'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Waste Container'

    name = fields.Char(
        string='Bin Number',
        required=True,
        # copy=False,
        readonly=True,
        default='New')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('waste.container') or 'New'
        return super().create(vals)
    pickup_point_id = fields.Many2one('pickup.point', string="Pickup Point", ondelete='cascade')
    pickup_point_ids = fields.Many2many(
        'pickup.point',
        'waste_container_pickup_rel',  # relation table name
        'container_id',  # column pointing to waste.container
        'pickup_point_id',  # column pointing to pickup.point
        string="Pickup Points",
        help="All pickup points associated with this container."
    )

    serial_no = fields.Char(string='Serial Number')

    sale_order_id = fields.Many2one('sale.order', string="Sales Order")
    image = fields.Image(string="Image")
    status = fields.Selection([
        ('in_use', 'InUse'),
        ('broken', 'Broken'),
        ('intact', 'Intact'),
        ('missing', 'Missing'),
        ('un_use', 'UnUse'),
    ], default='', string='Condition')

    hide_tank = fields.Boolean(compute='_compute_hide_container')
    hide_bin = fields.Boolean(compute='_compute_hide_container')

    # hide_hazardous = fields.Boolean(compute='_compute_hide_waste_type')

    @api.depends('container_type_id','container_type_id.name')
    def _compute_hide_container(self):
        for rec in self:
            is_tank = (rec.container_type_id.name or '').strip().lower()
            is_bin = (rec.container_type_id.name or '').strip().lower()
            rec.hide_tank = (is_tank == 'tank')
            rec.hide_bin = (is_bin == 'bin')


    container_type_id = fields.Many2one('container.type', string="Container Type")
    bin_type_id       = fields.Many2one('bin.type', string="Bin Type")
    tank_volume_id    = fields.Many2one('tank.volume', string="Tank Volume")
    display_info      = fields.Char(string="Bin / Volume Info", compute="_compute_display_info", store=True)

    @api.depends('container_type_id', 'bin_type_id', 'tank_volume_id')
    def _compute_display_info(self):
        for rec in self:
            ct_name = (rec.container_type_id.display_name or '').strip().lower()
            if ct_name == 'bin':
                rec.display_info = rec.bin_type_id.display_name or ''
            elif ct_name == 'tank':
                rec.display_info = rec.tank_volume_id.display_name or ''
            else:
                rec.display_info = ''

    inUse = fields.Boolean(string='InUse')

    customer_id = fields.Many2one('res.partner', string='Customer')
    color = fields.Integer("Color Index")

    lifted_service_id = fields.Many2one(
        'request.waste.service',
        string="Lifted In Service"
    )

    dropped_service_id = fields.Many2one(
        'request.waste.service',
        string="Dropped In Service"
    )

    shunt_service_id = fields.Many2one(
        'request.waste.service',
        string="Shunted In Service"
    )

    liters_collected = fields.Float(string="Liters Collected")
    liters_remaining = fields.Float(string="Liters Remaining", compute="_compute_liters_remaining", store=True)

    @api.depends('liters_collected', 'tank_volume_id')
    def _compute_liters_remaining(self):
        for rec in self:
            try:
                total = float(rec.tank_volume_id.replace('L', '')) if rec.tank_volume_id else 0
            except:
                total = 0
            rec.liters_remaining = max(0.0, total - rec.liters_collected)

    product_id = fields.Many2one('product.product', string="Related Product")


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    waste_container_ids = fields.Many2many(
        'waste.container',  # Target model
        'product_template_waste_container_rel',  # Relation table name
        # 'product_tmpl_id',  # Column for this model
        # 'container_id',  # Column for waste.container model
        string='Waste Containers'

    )
    partner_id = fields.Many2one('res.partner', string="Customer")
    pickup_point_id = fields.Many2one('pickup.point', string="Drop-off/Pickup Point", domain="[('partner_id', '=', partner_id)]")


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    customer_id = fields.Many2one('res.partner', string="Customer")
    pickup_point_id = fields.Many2one('pickup.point', string="Pickup Point")

    # waste_container_ids = fields.Many2many(
    #     'waste.container',
    #     'sale_order_line_waste_container_rel',  # relation table name
    #     'sale_order_line_id',  # column for this model
    #     'waste_container_id',  # column for related model
    #     string="Waste Containers"
    # )