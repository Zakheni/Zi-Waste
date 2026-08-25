"""Wizard to search and assign the closest licensed disposal site."""
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WasteRequestDisposalWizard(models.TransientModel):
    _name = 'waste.request.disposal.wizard'
    _description = 'Find Disposal Site for Waste Request'

    request_id = fields.Many2one(
        'waste.service.request',
        string='Service Request',
        required=True,
    )
    pickup_point_name = fields.Char(string='Pickup Point', readonly=True)
    job_address = fields.Text(string='Pickup location', readonly=True)
    job_latitude = fields.Float(digits=(10, 7), readonly=True)
    job_longitude = fields.Float(digits=(10, 7), readonly=True)
    waste_type_label = fields.Char(string='Waste Type', readonly=True)

    disposal_site_id = fields.Many2one(
        'waste.disposal.site',
        string='Selected Disposal Site',
    )
    site_candidate_ids = fields.One2many(
        'waste.request.disposal.wizard.line',
        'wizard_id',
        string='Nearest Disposal Sites',
    )
    map_data_json = fields.Text(string='Map Data')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context or {}
        request = False
        if ctx.get('active_model') == 'waste.service.request' and ctx.get('active_id'):
            request = self.env['waste.service.request'].browse(ctx['active_id'])
        elif res.get('request_id'):
            request = self.env['waste.service.request'].browse(res['request_id'])

        if request:
            location = request.get_pickup_job_location()
            waste_label = request.waste_type_id.name if request.waste_type_id else ''
            res.update({
                'request_id': request.id,
                'pickup_point_name': location.get('pickup_point_name') or '',
                'job_address': location.get('full_address') or location.get('display_name') or '',
                'job_latitude': location.get('lat') or 0.0,
                'job_longitude': location.get('lon') or 0.0,
                'waste_type_label': waste_label,
                'disposal_site_id': request.disposal_site_id.id or False,
            })
        return res

    def _waste_type_code(self):
        self.ensure_one()
        DisposalSite = self.env['waste.disposal.site']
        return DisposalSite._waste_type_code_from_manifest(self.request_id.waste_type_id)

    def _build_map_data(self):
        self.ensure_one()
        job = {
            'lat': self.job_latitude or 0,
            'lon': self.job_longitude or 0,
            'label': self.job_address or self.pickup_point_name or 'Pickup point',
        }
        providers = []
        for line in self.site_candidate_ids:
            label = line.site_id.site_code or line.site_id.name or 'Disposal site'
            providers.append({
                'id': line.site_id.id,
                'name': label,
                'address': line.site_address or '',
                'lat': line.latitude,
                'lon': line.longitude,
                'distance_km': line.distance_km,
                'rank': line.rank,
                'city': '',
            })
        return {'job': job, 'providers': providers}

    def _sync_map_data(self):
        for wizard in self:
            wizard.map_data_json = json.dumps(wizard._build_map_data())

    def _populate_site_candidates(self):
        """Rank licensed disposal sites by distance from the manifest pickup point."""
        self.ensure_one()
        if not self.request_id.pickup_point_ids:
            raise UserError(_("Please add at least one pickup point on the manifest first."))

        DisposalSite = self.env['waste.disposal.site']
        location = self.request_id.get_pickup_job_location(geocode=True)
        waste_type_code = self._waste_type_code()

        self.write({
            'job_address': location.get('full_address') or location.get('display_name') or '',
            'job_latitude': location.get('lat') or 0.0,
            'job_longitude': location.get('lon') or 0.0,
            'pickup_point_name': location.get('pickup_point_name') or '',
            'waste_type_label': self.request_id.waste_type_id.name if self.request_id.waste_type_id else '',
            'site_candidate_ids': [(5, 0, 0)],
        })

        ranked = DisposalSite.find_nearest_sites(
            job_lat=location.get('lat'),
            job_lon=location.get('lon'),
            waste_type_code=waste_type_code,
            limit=10,
            geocode_missing=True,
        )
        if not ranked:
            raise UserError(
                _("No disposal sites found for this waste type. "
                  "Create sites under Waste Management → Disposal Sites.")
            )

        lines = []
        for idx, row in enumerate(ranked, start=1):
            lines.append((0, 0, {
                'site_id': row['site_id'],
                'distance_km': row['distance_km'],
                'rank': idx,
            }))
        self.write({
            'site_candidate_ids': lines,
            'disposal_site_id': ranked[0]['site_id'],
        })
        self._sync_map_data()

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            if wizard.request_id and wizard.request_id.pickup_point_ids:
                try:
                    wizard._populate_site_candidates()
                except UserError:
                    wizard._sync_map_data()
        return wizards

    def action_search_sites(self):
        self.ensure_one()
        self._populate_site_candidates()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply_site(self):
        self.ensure_one()
        if not self.request_id:
            raise UserError(_("No related service request found."))
        if not self.disposal_site_id:
            raise UserError(_("Please search and select a disposal site first."))

        self.request_id.write({
            'disposal_site_id': self.disposal_site_id.id,
        })
        return {'type': 'ir.actions.act_window_close'}
