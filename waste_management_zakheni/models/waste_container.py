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

    container_type = fields.Selection([
        ('bin', 'Bin'),
        ('tank', 'Tank')
    ], String="container Type", default=''
    )
    bin_type = fields.Selection([
        ('6m³', '6m³'),
        ('9m³', '9m³'),
        ('11m³', '11m³'),
        ('18m³', '18m³'),
        ('28m³', '28m³'),
    ], default='',string="Bin Type")

    tank_volume = fields.Selection([
        ('7000_liters', '7000 Liters'),
        ('9000_liters', '9000 Liters'),
        ('11000_liters', '11000 Liters'),
        ('12000_liters', '12000 Liters'),
        ('15000_liters', '15000 Liters'),
    ],default='', string="Tank Volume",)

    # bin_type = fields.Selection([
    #     ('6m3', '6m³'),
    #     ('9m3', '9m³'),
    #     ('11m3', '11m³'),
    #     ('18m3', '18m³'),
    #     ('28m3', '28m³'),
    #
    # ], default='', string='Type', )
    # tank_volume = fields.Selection([
    #     ('7000L', '7000 Liters'),
    #     ('9000L', '9000 Liters'),
    #     ('11000L', '11000 Liters'),
    #     ('12000L', '12000 Liters'),
    #     ('15000L', '15000 Liters'),
    # ], default='', string='Tank Volume',
    # )

    display_info = fields.Char(string="Bin / Volume Info", compute="_compute_display_info", store=True)

    @api.depends('container_type', 'bin_type', 'tank_volume')
    def _compute_display_info(self):
        for rec in self:
            if rec.container_type == 'bin':
                rec.display_info = dict(type(rec).bin_type.selection).get(rec.bin_type, '')
            elif rec.container_type == 'tank':
                rec.display_info = dict(type(rec).tank_volume.selection).get(rec.tank_volume, '')
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

    @api.depends('liters_collected', 'tank_volume')
    def _compute_liters_remaining(self):
        for rec in self:
            try:
                total = float(rec.tank_volume.replace('L', '')) if rec.tank_volume else 0
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