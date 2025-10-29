from odoo import models, fields
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_container = fields.Boolean(string="Is a Container?")
    container_type = fields.Selection([
        ('bin', 'Bin'),
        ('tank', 'Tank')
    ], string="Container Type")

    bin_type = fields.Selection([...])
    tank_volume = fields.Selection([...])