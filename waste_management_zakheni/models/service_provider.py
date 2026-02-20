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
    _name = "wms.service.provider"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'
    _description = "Waste Service Provider"
    _order = "name"


    # Basic info
    name = fields.Char(string="Service Provider Name", required=True, tracking=True)
    street = fields.Char(string="Address", tracking=True)
    suburb = fields.Char(required=True, tracking=True)
    city = fields.Char(string="City/Town", required=True, tracking=True)
    province = fields.Selection(SA_PROVINCES, required=True, tracking=True)

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

    # Optional geo fields (for closest matching if you add coordinates later)
    latitude = fields.Float()
    longitude = fields.Float()

    _sql_constraints = [
        ("name_province_city_unique",
         "unique(name, province, city, suburb)",
         "This provider already exists for the same area."),
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

    # ---- Helper API ----
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
            def key_fn(p):
                if p.latitude or p.longitude:
                    return (p.latitude or 0.0) ** 2 + (p.longitude or 0.0) ** 2
                return p.name or ""
            providers = providers.sorted(key=key_fn)
        return providers[:1].id if providers else False

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
        for vals in vals_list:
            if not vals.get('company_id'):
                vals['company_id'] = self.env.company.id

            if vals.get('phone'):
                vals['phone'] = self._normalize_phone(vals['phone'])
            if vals.get('mobile'):
                vals['mobile'] = self._normalize_phone(vals['mobile'])

        records = super().create(vals_list)
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
        if vals.get('phone'):
            vals['phone'] = self._normalize_phone(vals['phone'])
        if vals.get('mobile'):
            vals['mobile'] = self._normalize_phone(vals['mobile'])
        return super().write(vals)

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