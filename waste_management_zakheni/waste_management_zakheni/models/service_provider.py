"""External service provider registry with SA province coverage."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re

SA_PROVINCES = [
    ("EC", "Eastern Cape"),
    ("FS", "Free State"),
    ("GP", "Gauteng"),
    ("KZN", "KwaZulu-Natal"),
    ("LP", "Limpopo"),
    ("MP", "Mpumalanga"),
    ("NC", "Northern Cape"),
    ("NW", "North West"),
    ("WC", "Western Cape"),
]

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'

class ServiceProvider(models.Model):
    """Third-party haulier invited to fulfil a manifest."""
    _name = "wms.service.provider"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'wmz.geo.mixin']
    _mail_post_access = 'read'
    _description = "Waste Service Provider"
    _order = "name"


    # Basic info
    name = fields.Char(string="Service Provider Name", required=True, tracking=True)
    full_address = fields.Text(
        string="Location",
        required=True,
        tracking=True,
        help="Enter the full address, e.g. 5 Dwerg St, Denver, Johannesburg, 2094, South Africa",
    )
    street = fields.Char(string="Street", tracking=True)
    suburb = fields.Char(tracking=True)
    city = fields.Char(string="City/Town", tracking=True)
    province = fields.Selection(SA_PROVINCES, tracking=True)

    agent = fields.Many2one(
        'res.users',
        string="Agent",
        domain=lambda self: [
            ('groups_id', 'in', self.env.ref('waste_management_zakheni.group_wmz_client_agent').id),
            ('company_ids', 'in', self.env.company.id),
        ]
    )


    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=False,
        default=lambda self: self.env.company,
        index=True
    )

    # Contacts
    phone = fields.Char(required=True, tracking=True)
    mobile = fields.Char(required=True, tracking=True)
    email = fields.Char(required=True, tracking=True)

    # Fleet info (reuse Fleet's Vehicle Model Categories as 'types')
    fleet_category_ids = fields.Many2many(
        "fleet.vehicle.model.category",
        "wms_provider_fleet_category_rel",
        "provider_id",
        "category_id",
        string="Fleet Categories")
    number_of_fleet = fields.Integer(string="Number of Fleet", default=0)
    fleet_category_list = fields.Char(
        string="Fleet Categories (List)",
        compute="_compute_fleet_category_list",
        store=False,
        help="Selected fleet categories as a comma-separated list.",
    )

    # Geo fields for map-based closest-provider matching
    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))
    geo_synced = fields.Boolean(
        string="Geocoded",
        compute="_compute_geo_synced",
        store=False,
    )

    _sql_constraints = [
        ("name_full_address_unique",
         "unique(name, full_address)",
         "This provider already exists at the same location."),
    ]

    @api.constrains("email")
    def _check_email(self):
        for rec in self:
            if rec.email and "@" not in rec.email:
                raise ValidationError(_("Please enter a valid email address."))

    @api.depends("fleet_category_ids")
    def _compute_fleet_category_list(self):
        for rec in self:
            rec.fleet_category_list = ", ".join(rec.fleet_category_ids.mapped("name"))

    @api.depends("latitude", "longitude")
    def _compute_geo_synced(self):
        for rec in self:
            rec.geo_synced = bool(rec.latitude and rec.longitude)

    def _province_label(self):
        self.ensure_one()
        return dict(SA_PROVINCES).get(self.province, self.province or "")

    def _build_full_address_from_parts(self):
        """Build full_address from legacy street/suburb/city/province fields."""
        self.ensure_one()
        parts = [
            self.street,
            self.suburb,
            self.city,
            self._province_label(),
            "South Africa",
        ]
        return ", ".join(p.strip() for p in parts if p and str(p).strip())

    def _apply_geocode_components(self, components):
        """Store parsed address parts returned by Nominatim."""
        self.ensure_one()
        if not components:
            return
        vals = {}
        if components.get("street") and not self.street:
            vals["street"] = components["street"]
        if components.get("suburb") and not self.suburb:
            vals["suburb"] = components["suburb"]
        if components.get("city") and not self.city:
            vals["city"] = components["city"]
        if components.get("province") and not self.province:
            vals["province"] = components["province"]
        if vals:
            super(ServiceProvider, self).write(vals)

    def _geocode_self(self, force=False):
        """Geocode this provider's address and store lat/lon."""
        self.ensure_one()
        geo = self.env["wmz.geo.mixin"]
        query = (self.full_address or "").strip() or self._build_full_address_from_parts()
        if not query:
            return {"lat": False, "lon": False, "approximate": False}
        result = geo.geocode_query(query)
        if result.get("lat") and result.get("lon"):
            self.write({
                "latitude": result["lat"],
                "longitude": result["lon"],
            })
            self._apply_geocode_components(result.get("components"))
        return result

    def action_geocode_address(self):
        """Button: geocode provider address via OpenStreetMap."""
        for rec in self:
            result = rec._geocode_self(force=True)
            if not result.get("lat"):
                raise ValidationError(
                    _("Could not locate this address on the map. Check spelling and use a format like "
                      "'5 Dwerg St, Denver, Johannesburg, 2094, South Africa'.")
                )
            if result.get("approximate"):
                rec.message_post(
                    body=_(
                        "Approximate map location used (exact street not found in OpenStreetMap): %s"
                    ) % (result.get("display_name") or rec.full_address),
                    message_type="notification",
                )
        return True

    @api.model
    def _ensure_provider_coordinates(self, providers):
        """Ensure providers have coordinates; geocode missing ones."""
        for provider in providers:
            if provider.latitude and provider.longitude:
                continue
            provider._geocode_self()
        return providers

    @api.model
    def find_nearest_providers(
        self,
        job_lat=False,
        job_lon=False,
        limit=10,
        required_categories=None,
        province_code=None,
        city=None,
        suburb=None,
    ):
        """Return providers sorted by distance (km) to the job site — closest first."""
        providers = self.search([])
        if required_categories:
            providers = providers.filtered(
                lambda p: set(required_categories).issubset(set(p.fleet_category_ids.ids))
            )
        if not providers:
            return []

        if job_lat and job_lon:
            providers = self._ensure_provider_coordinates(providers)
            ranked = []
            for provider in providers:
                if not provider.latitude or not provider.longitude:
                    continue
                distance = self.haversine_km(
                    job_lat, job_lon, provider.latitude, provider.longitude
                )
                ranked.append({
                    "provider": provider,
                    "provider_id": provider.id,
                    "distance_km": round(distance, 2),
                })
            ranked.sort(key=lambda x: x["distance_km"])
            return ranked[:limit]

        # Text fallback when geocoding the job site failed
        provider_id = self.find_best_provider(province_code, city, suburb, required_categories)
        if not provider_id:
            return []
        provider = self.browse(provider_id)
        return [{
            "provider": provider,
            "provider_id": provider.id,
            "distance_km": 0.0,
        }]

    # ---- Helper API (text fallback) ----
    @api.model
    def find_best_provider(self, province_code, city, suburb=None, required_categories=None):
        """Find a provider for a request location.
        Priority:
          1) Exact match on province+city+suburb (if provided)
          2) Exact match on province+city
          3) Exact match on province only
        If required_categories are provided, providers must include all of them.
        If multiple matches exist and lat/long are set, choose the closest to (0,0)
        or use the first by name as a deterministic fallback.
        """
        domain = [("province", "=", province_code)]
        providers = self.search(domain)
        if not providers:
            return False

        # filter by categories if provided
        if required_categories:
            providers = providers.filtered(
                lambda p: set(required_categories).issubset(set(p.fleet_category_ids.ids))
            )
            if not providers:
                return False

        # Narrow by city
        city_matches = providers.filtered(lambda p: (p.city or "").strip().lower() == (city or "").strip().lower())
        if city_matches:
            providers = city_matches
        # Narrow by suburb
        if suburb:
            suburb_matches = providers.filtered(lambda p: (p.suburb or "").strip().lower() == (suburb or "").strip().lower())
            if suburb_matches:
                providers = suburb_matches

        if len(providers) > 1:
            providers = providers.sorted(key=lambda p: p.name or "")
        return providers[:1].id if providers else False

    @api.model
    def _backfill_full_address(self):
        """Populate full_address on legacy provider records."""
        for rec in self.with_context(active_test=False).search([
            "|", ("full_address", "=", False), ("full_address", "=", ""),
        ]):
            full = rec._build_full_address_from_parts()
            if full:
                rec.write({"full_address": full})

    def action_open_find_wizard(self):
        """Open the 'Find Provider' wizard from a button."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Find Provider",
            "res_model": "wms.service.provider.select.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_province": self.province,
                "default_city": self.city,
                "default_suburb": self.suburb,
                # If you want to pre-filter by categories too:
                # "default_required_category_ids": [(6, 0, self.fleet_category_ids.ids)],
            },
        }

    # @api.model
    # def create(self, vals):
    #     if not vals.get('company_id'):
    #         vals['company_id'] = self.env.company.id
    #     return super().create(vals)

    def _normalize_phone(self, value):
        """
        Normalize phone numbers by removing spaces, dashes, and brackets.

        +27 12 345 6789  → +27123456789
        (+27)12-345-6789 → +27123456789
        """
        if not value:
            return value
        return re.sub(r'[\s\-\(\)]+', '', value)

        # ------------------------------------------------------------
        # CREATE: normalize BEFORE constraint
        # ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Validate provider data and assign sequence on create."""
        for vals in vals_list:
            if not vals.get('company_id'):
                vals['company_id'] = self.env.company.id

            if vals.get('phone'):
                vals['phone'] = self._normalize_phone(vals['phone'])
            if vals.get('mobile'):
                vals['mobile'] = self._normalize_phone(vals['mobile'])

            if not vals.get('full_address'):
                parts = [
                    vals.get('street'),
                    vals.get('suburb'),
                    vals.get('city'),
                    dict(SA_PROVINCES).get(vals.get('province'), vals.get('province')),
                    'South Africa',
                ]
                vals['full_address'] = ", ".join(
                    p.strip() for p in parts if p and str(p).strip()
                )

        records = super().create(vals_list)
        for rec in records:
            rec._geocode_self()
        return records

    # @api.model_create_multi
    # def create(self, vals_list):
    #     for vals in vals_list:
    #         if vals.get('phone'):
    #             vals['phone'] = self._normalize_phone(vals['phone'])
    #         if vals.get('mobile'):
    #             vals['mobile'] = self._normalize_phone(vals['mobile'])
    #     return super().create(vals_list)

    # ------------------------------------------------------------
    # WRITE: normalize BEFORE constraint
    # ------------------------------------------------------------
    def write(self, vals):
        """Track provider changes in the chatter."""
        if vals.get('phone'):
            vals['phone'] = self._normalize_phone(vals['phone'])
        if vals.get('mobile'):
            vals['mobile'] = self._normalize_phone(vals['mobile'])
        res = super().write(vals)
        if "full_address" in vals:
            super(ServiceProvider, self).write({"latitude": 0.0, "longitude": 0.0})
            for rec in self:
                rec._geocode_self()
        elif any(k in vals for k in ("street", "suburb", "city", "province")):
            for rec in self.filtered(lambda r: not r.full_address):
                rec.full_address = rec._build_full_address_from_parts()
            for rec in self.filtered(lambda r: not r.latitude or not r.longitude):
                rec._geocode_self()
        return res

    # ------------------------------------------------------------
    # CONSTRAINT: validate normalized value ONLY
    # ------------------------------------------------------------
    @api.constrains('phone', 'mobile')
    def _check_phone_country_code(self):
        for partner in self:
            for field in ('phone', 'mobile'):
                value = partner[field]
                if not value:
                    continue

                if not re.match(r'^\+\d{7,15}$', value):
                    raise ValidationError(
                        _("Phone number must include country code, e.g. +27 12 345 6789, (+27)12-345-6789 and +27123456789 ✅ "
                          "\n and it must not include Alpha numeric ❌ ")
                    )

    # @api.constrains('email')
    # def _check_email_required(self):
    #     for partner in self:
    #         # Skip contacts that are not real business partners
    #         if partner.is_company or partner.customer_rank > 0 or partner.supplier_rank > 0:
    #             if not partner.email:
    #                 raise ValidationError(
    #                     _("Email address is required. ⚠️")
    #                 )

    @api.constrains('email')
    def _check_email_required(self):
        for rec in self:
            if not rec.email:
                raise ValidationError(
                    _("Email address is required.")
                )

    @api.constrains('email')
    def _check_email_format(self):
        for partner in self:
            if partner.email:
                email = partner.email.strip()
                if not re.match(EMAIL_REGEX, email):
                    raise ValidationError(
                        _("Invalid work email address format e.g email must take this format ✅'email@example.com' not this ❌ %s ") % email

                    )