
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

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

class ServiceProvider(models.Model):
    _name = "wms.service.provider"
    _description = "Waste Service Provider"
    _order = "name"

    # Basic info
    name = fields.Char(string="Service Provider Name", required=True)
    street = fields.Char(string="Address")
    suburb = fields.Char(required=True)
    city = fields.Char(string="City/Town", required=True)
    province = fields.Selection(SA_PROVINCES, required=True)

    # Contacts
    phone = fields.Char(required=True)
    mobile = fields.Char()
    email = fields.Char()

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




#
# from odoo import api, fields, models, _
# from odoo.exceptions import ValidationError
#
# SA_PROVINCES = [
#     ("EC", "Eastern Cape"),
#     ("FS", "Free State"),
#     ("GP", "Gauteng"),
#     ("KZN", "KwaZulu-Natal"),
#     ("LP", "Limpopo"),
#     ("MP", "Mpumalanga"),
#     ("NC", "Northern Cape"),
#     ("NW", "North West"),
#     ("WC", "Western Cape"),
# ]
#
# class FleetType(models.Model):
#     _name = "wms.fleet.type"
#     _description = "Fleet Type (Vehicle Category)"
#     _order = "name"
#
#     name = fields.Char(required=True)
#     description = fields.Text()
#
# class ServiceProvider(models.Model):
#     _name = "wms.service.provider"
#     _description = "Waste Service Provider"
#     _order = "name"
#
#     # Basic info
#     name = fields.Char(string="Service Provider Name", required=True)
#     street = fields.Char(string="Address")
#     suburb = fields.Char(required=True)
#     city = fields.Char(string="City/Town", required=True)
#     province = fields.Selection(SA_PROVINCES, required=True)
#
#     # Contacts
#     phone = fields.Char(required=True)
#     mobile = fields.Char()
#     email = fields.Char()
#
#     # Fleet info
#     number_of_fleet = fields.Integer(string="Number of Fleet", default=0)
#     fleet_type_ids = fields.Many2many("wms.fleet.type", string="Fleet Type")
#     fleet_type_list = fields.Char(
#         string="Fleet Type (List)",
#         compute="_compute_fleet_type_list",
#         store=False,
#         help="Convenience field to display selected fleet types as comma-separated list.",
#     )
#
#     # Optional geo fields (for 'closest' selection if lat/long available)
#     latitude = fields.Float()
#     longitude = fields.Float()
#
#     _sql_constraints = [
#         ("name_province_city_unique",
#          "unique(name, province, city, suburb)",
#          "This provider already exists for the same area."),
#     ]
#
#     @api.constrains("email")
#     def _check_email(self):
#         for rec in self:
#             if rec.email and "@" not in rec.email:
#                 raise ValidationError(_("Please enter a valid email address."))
#
#     @api.depends("fleet_type_ids")
#     def _compute_fleet_type_list(self):
#         for rec in self:
#             rec.fleet_type_list = ", ".join(rec.fleet_type_ids.mapped("name"))
#
#     # ---- Helper API ----
#     @api.model
#     def find_best_provider(self, province_code, city, suburb=None):
#         """Find a provider for a request location.
#         Priority:
#           1) Exact match on province+city+suburb (if provided)
#           2) Exact match on province+city
#           3) Exact match on province only
#         If multiple matches exist and lat/long are set, choose the closest to (0,0)
#         or use the first by name as a deterministic fallback.
#         """
#         domain = [("province", "=", province_code)]
#         providers = self.search(domain)
#         if not providers:
#             return False
#         # Narrow by city
#         city_matches = providers.filtered(lambda p: (p.city or "").strip().lower() == (city or "").strip().lower())
#         if city_matches:
#             providers = city_matches
#         # Narrow by suburb
#         if suburb:
#             suburb_matches = providers.filtered(lambda p: (p.suburb or "").strip().lower() == (suburb or "").strip().lower())
#             if suburb_matches:
#                 providers = suburb_matches
#
#         # If multiple, try to use coordinates (optional). Fallback to name.
#         if len(providers) > 1:
#             def key_fn(p):
#                 if p.latitude or p.longitude:
#                     # distance to origin (placeholder unless you add request coords)
#                     return (p.latitude or 0.0) ** 2 + (p.longitude or 0.0) ** 2
#                 return p.name or ""
#             providers = providers.sorted(key=key_fn)
#         return providers[:1].id if providers else False
