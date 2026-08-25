"""Transient lines for ranked disposal site candidates."""
from odoo import fields, models


class WasteRequestDisposalWizardLine(models.TransientModel):
    _name = 'waste.request.disposal.wizard.line'
    _description = 'Disposal Site Candidate'
    _order = 'rank asc, distance_km asc'

    wizard_id = fields.Many2one(
        'waste.request.disposal.wizard',
        required=True,
        ondelete='cascade',
    )
    site_id = fields.Many2one('waste.disposal.site', required=True)
    site_name = fields.Char(related='site_id.site_code')
    site_display = fields.Char(related='site_id.display_name', string='Site')
    site_address = fields.Text(related='site_id.full_address', string='Location')
    site_waste_type = fields.Selection(related='site_id.waste_type', string='Waste Type')
    capacity_tons = fields.Float(related='site_id.capacity_tons')
    distance_km = fields.Float(string='Distance (km)', digits=(10, 2))
    rank = fields.Integer(string='#')
    latitude = fields.Float(related='site_id.latitude')
    longitude = fields.Float(related='site_id.longitude')

    def action_select(self):
        self.ensure_one()
        self.wizard_id.write({'disposal_site_id': self.site_id.id})
        self.wizard_id._sync_map_data()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'waste.request.disposal.wizard',
            'res_id': self.wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }
