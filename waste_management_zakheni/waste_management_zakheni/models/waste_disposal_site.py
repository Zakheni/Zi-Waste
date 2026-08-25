"""Licensed disposal sites filtered by waste type."""
import json

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DisposalSite(models.Model):
    """Destination facility for hazardous and general waste disposal."""
    _name = 'waste.disposal.site'
    _description = 'Waste Disposal Site'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'wmz.geo.mixin']
    _order = 'site_code, name'

    name = fields.Char(
        string='Reference',
        readonly=True,
        default='New',
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        index=True,
        default=lambda self: self.env.company,
    )
    site_code = fields.Char(string='Site Code', tracking=True)
    full_address = fields.Text(
        string='Location',
        tracking=True,
        help="Full address, e.g. Landfill Rd, Germiston, 1401, South Africa",
    )
    location = fields.Char(
        string='Location (legacy)',
        help='Deprecated — use Location (full address). Kept for migration.',
    )
    waste_type = fields.Selection([
        ('hazardous', 'Hazardous'),
        ('general_non-compactable', 'General Non-Compactable'),
        ('general_compactable', 'General Compactable'),
        ('none', 'None'),
    ], string='Waste Type', tracking=True)

    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))
    geo_synced = fields.Boolean(
        string='Geocoded',
        compute='_compute_geo_synced',
        store=False,
    )
    map_preview_json = fields.Text(
        string='Map Preview',
        compute='_compute_map_preview_json',
        store=False,
    )

    capacity_tons = fields.Float(string='Capacity (tons)')
    current_load = fields.Float(string='Current Load (tons)')
    contact_person = fields.Char()
    phone = fields.Char()
    email = fields.Char()
    license_number = fields.Char()
    inspection_date = fields.Date()
    next_inspection_date = fields.Date()
    notes = fields.Html(
        string='Service Notes',
        sanitize=True,
        sanitize_tags=False,
        sanitize_attributes=False,
        sanitize_style=True,
        translate=True,
    )
    active = fields.Boolean(default=True)

    @api.depends('latitude', 'longitude')
    def _compute_geo_synced(self):
        for rec in self:
            rec.geo_synced = bool(rec.latitude and rec.longitude)

    @api.depends('latitude', 'longitude', 'full_address', 'site_code', 'name')
    def _compute_map_preview_json(self):
        for rec in self:
            if rec.latitude and rec.longitude:
                label = rec.full_address or rec.site_code or rec.name or 'Disposal site'
                rec.map_preview_json = json.dumps({
                    'job': {
                        'lat': rec.latitude,
                        'lon': rec.longitude,
                        'label': label,
                    },
                    'providers': [],
                })
            else:
                rec.map_preview_json = ''

    def name_get(self):
        result = []
        waste_labels = dict(self._fields['waste_type'].selection)
        for rec in self:
            parts = [p for p in (rec.site_code, rec.name) if p and p != 'New']
            label = ' — '.join(parts) if parts else rec.name or _('Disposal Site')
            if rec.waste_type:
                label = f"{label} [{waste_labels.get(rec.waste_type, rec.waste_type)}]"
            result.append((rec.id, label))
        return result

    @api.model
    def _waste_type_code_from_manifest(self, waste_type_record):
        """Map waste.type record to disposal site waste_type selection."""
        if not waste_type_record:
            return False
        waste_name = (waste_type_record.name or '').strip().lower()
        if waste_name == 'hazardous':
            return 'hazardous'
        if waste_name == 'general compactable':
            return 'general_compactable'
        if waste_name == 'general non-compactable':
            return 'general_non-compactable'
        return False

    @api.model
    def _domain_for_waste_type(self, waste_type_code):
        """Sites allowed for a given waste type code (matches manifest filter logic)."""
        if not waste_type_code:
            return []
        return [
            '|',
            ('waste_type', '=', waste_type_code),
            ('waste_type', '=', False),
        ]

    @api.model
    def _ensure_site_coordinates(self, sites):
        for site in sites:
            if site.latitude and site.longitude:
                continue
            site._geocode_self()
        return sites

    @api.model
    def find_nearest_sites(self, job_lat=False, job_lon=False, waste_type_code=None, limit=10,
                           geocode_missing=False):
        """Return disposal sites sorted by distance (km) — closest first."""
        domain = self._domain_for_waste_type(waste_type_code) if waste_type_code else []
        sites = self.search(domain)
        if not sites:
            return []

        if job_lat and job_lon:
            if geocode_missing:
                sites = self._ensure_site_coordinates(sites)
            ranked = []
            for site in sites:
                if not site.latitude or not site.longitude:
                    continue
                distance = self.haversine_km(
                    job_lat, job_lon, site.latitude, site.longitude
                )
                ranked.append({
                    'site': site,
                    'site_id': site.id,
                    'distance_km': round(distance, 2),
                })
            ranked.sort(key=lambda x: x['distance_km'])
            return ranked[:limit]

        return [{
            'site': site,
            'site_id': site.id,
            'distance_km': 0.0,
        } for site in sites[:limit]]

    @api.model
    def _backfill_full_address(self):
        for rec in self.with_context(active_test=False).search([
            '|', ('full_address', '=', False), ('full_address', '=', ''),
        ]):
            if rec.location:
                rec.write({'full_address': rec.location.strip()})

    def _geocode_self(self):
        self.ensure_one()
        query = (self.full_address or '').strip() or (self.location or '').strip()
        if not query:
            return {'lat': False, 'lon': False, 'approximate': False}
        result = self.env['wmz.geo.mixin'].geocode_query(query)
        if result.get('lat') and result.get('lon'):
            self.write({
                'latitude': result['lat'],
                'longitude': result['lon'],
            })
        return result

    def action_geocode_address(self):
        for rec in self:
            result = rec._geocode_self()
            if not result.get('lat'):
                raise ValidationError(
                    _("Could not locate this address on the map. Enter a full location such as "
                      "'Landfill Rd, Germiston, 1401, South Africa' and try again.")
                )
            if result.get('approximate'):
                rec.message_post(
                    body=_(
                        "Approximate map location used (exact street not found in OpenStreetMap): %s"
                    ) % (result.get('display_name') or rec.full_address),
                    message_type='notification',
                )
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('waste.disposal.site') or 'New'
            if not vals.get('company_id'):
                vals['company_id'] = self.env.company.id
            if not vals.get('full_address') and vals.get('location'):
                vals['full_address'] = vals['location']
        records = super().create(vals_list)
        for rec in records:
            rec._geocode_self()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'full_address' in vals:
            super(DisposalSite, self).write({'latitude': 0.0, 'longitude': 0.0})
            for rec in self:
                rec._geocode_self()
        elif 'location' in vals:
            for rec in self.filtered(lambda r: not r.full_address and r.location):
                rec.full_address = rec.location
            for rec in self.filtered(lambda r: not r.latitude or not r.longitude):
                rec._geocode_self()
        return res
