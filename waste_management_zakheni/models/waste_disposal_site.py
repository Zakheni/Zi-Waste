from odoo import models, fields, api


class DisposalSite(models.Model):
    _name = 'waste.disposal.site'
    _description = 'Waste Disposal Site'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name_custom'


    name = fields.Char(
        string='Request ID',
        required=False,
        # copy=False,
        readonly=True,
        default='New')

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        default=lambda self: self.env.company,
        required=False,  # ✅ allow global/shared records
    )
    site_code = fields.Char()
    location = fields.Char()
    waste_type = fields.Selection([
        ('hazardous', 'Hazardous'),
        ('general_non-compactable', 'General Non-Compactable'),
        ('general_compactable', 'General Compactable'),
        ('none', 'None')
    ], string="Waste Type")

    display_name_custom = fields.Char(
        string="Display Name",
        compute="_compute_display_name_custom",
        store=True
    )

    @api.depends('site_code', 'name', 'waste_type')
    def _compute_display_name_custom(self):

        selection_dict = dict(self._fields['waste_type'].selection)

        for rec in self:
            waste_label = selection_dict.get(rec.waste_type, '')

            base_name = rec.site_code or rec.name or ''

            rec.display_name_custom = f"{base_name} [{waste_label}]"


    capacity_tons = fields.Float()
    current_load = fields.Float()
    contact_person = fields.Char()
    phone = fields.Char()
    email = fields.Char()
    license_number = fields.Char()
    inspection_date = fields.Date()
    next_inspection_date = fields.Date()
    notes = fields.Html(
        string="Service Notes",
        sanitize=True,     # removes unsafe tags like <script>
        sanitize_tags=False, # if you want to allow all tags
        sanitize_attributes=False,
        sanitize_style=True,
        translate=True     # allow trans
    )
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id)
    active = fields.Boolean(default=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('waste.disposal.site') or 'New'

        # create container for logged in company
        if not vals.get('company_id'):
            vals['company_id'] = self.env.company.id

        return super().create(vals)
