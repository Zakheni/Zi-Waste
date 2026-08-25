"""Wizard to search and assign the closest external service provider."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .service_provider import SA_PROVINCES


class WasteRequestProviderWizard(models.TransientModel):
    """Find providers by map distance and link to a manifest."""
    _name = "waste.request.provider.wizard"
    _description = "Find Service Provider for Waste Request"

    request_id = fields.Many2one(
        "waste.service.request",
        string="Service Request",
        required=True,
    )
    pickup_point_name = fields.Char(string="Pickup Point", readonly=True)
    job_address = fields.Text(string="Pickup location", readonly=True)
    job_display_name = fields.Char(string="Job Location", readonly=True)
    job_latitude = fields.Float(string="Job Latitude", digits=(10, 7), readonly=True)
    job_longitude = fields.Float(string="Job Longitude", digits=(10, 7), readonly=True)

    province = fields.Selection(SA_PROVINCES, string="Province")
    city = fields.Char(string="City")
    suburb = fields.Char(string="Suburb")

    provider_id = fields.Many2one(
        "wms.service.provider",
        string="Selected Provider",
    )
    provider_candidate_ids = fields.One2many(
        "waste.request.provider.wizard.line",
        "wizard_id",
        string="Nearest Providers",
    )
    map_data_json = fields.Text(string="Map Data")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context or {}
        request = False
        if ctx.get("active_model") == "waste.service.request" and ctx.get("active_id"):
            request = self.env["waste.service.request"].browse(ctx["active_id"])
        elif res.get("request_id"):
            request = self.env["waste.service.request"].browse(res["request_id"])

        if request:
            res["request_id"] = request.id
            location = request.get_pickup_job_location()
            res.update({
                "pickup_point_name": location.get("pickup_point_name") or "",
                "job_address": location.get("full_address") or location.get("display_name") or "",
                "job_display_name": location.get("display_name") or "",
                "job_latitude": location.get("lat") or 0.0,
                "job_longitude": location.get("lon") or 0.0,
                "province": location.get("province") or False,
                "city": location.get("city") or "",
                "suburb": location.get("suburb") or "",
            })
        return res

    def _build_map_data(self):
        self.ensure_one()
        job = {
            "lat": self.job_latitude or 0,
            "lon": self.job_longitude or 0,
            "label": self.job_address or self.job_display_name or self.pickup_point_name or "Pickup point",
        }
        providers = []
        for line in self.provider_candidate_ids:
            providers.append({
                "id": line.provider_id.id,
                "name": line.provider_name,
                "address": line.provider_address or "",
                "lat": line.latitude,
                "lon": line.longitude,
                "distance_km": line.distance_km,
                "rank": line.rank,
                "city": line.provider_city or "",
            })
        return {"job": job, "providers": providers}

    def _sync_map_data(self):
        for wizard in self:
            import json
            wizard.map_data_json = json.dumps(wizard._build_map_data())

    def action_search_providers(self):
        """Geocode job site and rank providers by distance."""
        self.ensure_one()
        if not self.request_id.pickup_point_ids:
            raise UserError(_("Please add at least one pickup point on the manifest first."))

        Provider = self.env["wms.service.provider"]
        location = self.request_id.get_pickup_job_location(geocode=True)
        self.write({
            "job_address": location.get("full_address") or location.get("display_name") or "",
            "job_display_name": location.get("display_name") or "",
            "job_latitude": location.get("lat") or 0.0,
            "job_longitude": location.get("lon") or 0.0,
            "pickup_point_name": location.get("pickup_point_name") or "",
            "province": location.get("province") or self.province,
            "city": location.get("city") or self.city,
            "suburb": location.get("suburb") or self.suburb,
            "provider_candidate_ids": [(5, 0, 0)],
        })

        ranked = Provider.find_nearest_providers(
            job_lat=location.get("lat"),
            job_lon=location.get("lon"),
            limit=10,
            province_code=self.province,
            city=self.city,
            suburb=self.suburb,
        )
        if not ranked:
            raise UserError(_("No service providers found. Create providers under Waste Management → Service Providers."))

        lines = []
        for idx, row in enumerate(ranked, start=1):
            lines.append((0, 0, {
                "provider_id": row["provider_id"],
                "distance_km": row["distance_km"],
                "rank": idx,
            }))
        self.write({
            "provider_candidate_ids": lines,
            "provider_id": ranked[0]["provider_id"],
        })
        self._sync_map_data()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_select_provider(self, provider_id=None):
        """Select a provider from the ranked list or map click."""
        self.ensure_one()
        pid = provider_id or self.provider_id.id
        if not pid:
            raise UserError(_("Please search for providers or select one from the list."))
        self.provider_id = pid
        self._sync_map_data()
        return True

    def action_apply_provider(self):
        """Apply selected provider to the manifest and close."""
        self.ensure_one()
        if not self.request_id:
            raise UserError(_("No related service request found."))
        if not self.provider_id:
            raise UserError(_("Please search and select a provider first."))

        line = self.provider_candidate_ids.filtered(lambda l: l.provider_id == self.provider_id)[:1]
        distance = line.distance_km if line else 0.0

        self.request_id.write({
            "is_service_provider": True,
            "provider_id": self.provider_id.id,
            "provider_distance_km": distance,
            "vehicle_id": False,
            "trailer_id": False,
        })
        return {"type": "ir.actions.act_window_close"}

    @api.model
    def get_provider_map_data(self, wizard_id):
        wizard = self.browse(wizard_id)
        if not wizard.exists():
            return {"job": {}, "providers": []}
        if not wizard.map_data_json:
            wizard._sync_map_data()
        import json
        try:
            return json.loads(wizard.map_data_json or "{}")
        except json.JSONDecodeError:
            return wizard._build_map_data()
