"""Waste service request (manifest) model and workflow.

Central record linking customers, containers, worksheets, sale orders,
and billing. Drives the full manifest lifecycle from draft through authorisation.
"""
import re
import logging
import json
import urllib.parse
from datetime import datetime, timedelta, time

from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError
from .service_provider import SA_PROVINCES

# from datetime import timedelta


_logger = logging.getLogger(__name__)

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'

class WasteServiceRequest(models.Model):
    """Main manifest record for waste collection and disposal jobs."""
    _name = 'waste.service.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Waste Service Request'

    name = fields.Char(
        string='Request ID',
        required=True,
        # copy=False,
        readonly=True,
        default='New')
    pickup_point_id = fields.Many2one('pickup.point', string="Pickup Point", ondelete='cascade')

    # company_id = fields.Many2one(
    #     'res.company',
    #     string='Company',
    #     default=lambda self: self.env.company,
    #     index=True,
    # )
    company_id = fields.Many2one(
        "res.company",
        required=False,
        default=lambda self: self.env.company,
        index=True,
    )


    invoice_ids = fields.One2many(
        "account.move",
        "service_request_id",
        string="Invoices",
        readonly=True,
    )

    invoice_count = fields.Integer(
        string="Invoices",
        compute="_compute_invoice_count",
    )

    def _compute_invoice_count(self):
        """Count linked customer invoices for the smart button."""
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    service_request_date = fields.Datetime(
        string='Service Request Date',
        default=fields.Datetime.now,  # use datetime imported from datetime
    )

    container_id = fields.Many2one('waste.container', string='Container')


    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        domain="['&', ('is_company', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    portal_user_id = fields.Many2one(
        'res.users',
        string="Portal User",
        help="Portal user who logged the request"
    )

    pickup_id = fields.Char(string="Pickup Point Name", related='pickup_point_id.name', )
    planned_date = fields.Datetime(string='Planned Date', tracking=True)

    quote_no = fields.Char(string="Quote No.")
    service_description = fields.Text(string='Service Description')
    UN_No_SIN_No = fields.Char(string='UN No/SIN No')
    waste_profile_Data_sheet_No = fields.Char(string='Waste Profile/Data sheet No')
    DTNumber = fields.Char(string='DTNumber')
    # disposal_site_id = fields.Many2one('waste.disposal.site', string="Disposal Side")

    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehicle Registration Number",
    )
    employee_id = fields.Many2one('hr.employee', string="Employee")
    driver_id = fields.Many2one(string="Driver", related="vehicle_id.driver_id", store=True)
    assistance_id = fields.Many2one(string="Driver Assistance", related="vehicle_id.future_driver_id")
    trailer_id = fields.Many2one("fleet.vehicle", string="Trailer Registration Number")
    number_of_bins = fields.Integer(
        string="Number of Bins",
        default=1,
        tracking=True,
    )

    number_of_bins_o = fields.Integer(
        related='order_line_id.number_of_bins',
        store=False,
        readonly=False,
    )

    work_sheet_id = fields.Many2one(
        "waste.worksheet",
        string="Work Sheet",
        ondelete="set null"
    )
    driver_signature = fields.Binary(string="Driver Signature")

    is_rejected = fields.Boolean(
        string="Ever Rejected",
        default=False,
        tracking=True,
        help="Ticked automatically if this request has ever been rejected.",
    )
    reject_reason = fields.Text(string="Enter Reject Reason", tracking=True, store=True)
    amend_comment = fields.Text(string="Enter Amend Comment", tracking=True, store=True)
    # driver_work_email = fields.Char(string="Driver Work email", related="employee_id.work_email", store=True)
    driver_work_email = fields.Char(
        related="driver_id.email",
        store=True
    )

    employee_email_id = fields.Many2one(
        'hr.employee',
        string="Mailto",
        domain=lambda self: self.env['hr.employee']._notification_recipient_domain(
            'waste_management_zakheni.group_wmz_admin_clerk'
        ),
    )

    admin_clerck_email = fields.Char(
        related="employee_email_id.work_email",
        store=True
    )

    employee_manager_id = fields.Many2one(
        'hr.employee',
        string="Mailto",
        domain=lambda self: self.env['hr.employee']._notification_recipient_domain(
            'waste_management_zakheni.group_wmz_user_manager',
            job_name='Manager',
        ),
    )

    manager_email = fields.Char(
        related="employee_manager_id.work_email",
        store=True
    )

    from_portal = fields.Boolean(
        string="Created from portal",
        default=False,
        help="Marked True when the service request is logged from the customer portal.",
    )

    finance_employee_id = fields.Many2one('hr.employee', string="Mailto")
    finance_email = fields.Char(related="finance_employee_id.work_email")

    # disposal_site_id = fields.Many2one(
    #     'waste.disposal.site',
    #     string="Disposal Site",
    #     domain="[('id', 'in', allowed_disposal_site_ids)]"
    # )

    disposal_site_id = fields.Many2one(
        'waste.disposal.site',
        string="Disposal Site",
        domain="[('id', 'in', allowed_disposal_site_ids)]"
    )

    # disposal_site_ids = fields.Many2many(
    #     'waste.disposal.site',
    #     'waste_request_disposal_site_rel',
    #     'request_id',
    #     'disposal_site_id',
    #     string="Disposal Sites",
    #     domain="[('id', 'in', allowed_disposal_site_ids)]"
    # )

    allowed_disposal_site_ids = fields.Many2many(
        'waste.disposal.site',
        compute='_compute_disposal_site_geo',
        string="Allowed Disposal Sites",
        store=False
    )
    disposal_site_distance_km = fields.Float(
        string='Disposal Site Distance (km)',
        compute='_compute_disposal_site_geo',
        readonly=True,
    )
    disposal_map_data_json = fields.Text(
        string='Disposal Map Data',
        compute='_compute_disposal_site_geo',
    )
    nearest_disposal_sites_summary = fields.Text(
        string='Nearest Disposal Sites',
        compute='_compute_disposal_site_geo',
        readonly=True,
    )


    # @api.depends('waste_type_id')
    # def _compute_allowed_disposal_sites(self):
    #
    #     DisposalSite = self.env['waste.disposal.site']
    #
    #     for rec in self:
    #
    #         if not rec.waste_type_id:
    #             rec.allowed_disposal_site_ids = DisposalSite.search([])
    #             continue
    #
    #         waste_name = (rec.waste_type_id.name or '').strip().lower()
    #
    #         # Hazardous
    #         if waste_name == 'hazardous':
    #
    #             sites = DisposalSite.search([
    #                 ('waste_type', '=', 'hazardous')
    #             ])
    #
    #         # General Compactable
    #         elif waste_name == 'general compactable':
    #
    #             sites = DisposalSite.search([
    #                 ('waste_type', '=', 'general_compactable')
    #             ])
    #
    #         # General Non-Compactable
    #         elif waste_name == 'general non-compactable':
    #
    #             sites = DisposalSite.search([
    #                 ('waste_type', '=', 'general_non-compactable')
    #             ])
    #
    #         else:
    #             sites = DisposalSite.search([])
    #
    #         rec.allowed_disposal_site_ids = sites


    # @api.onchange('waste_type_id')
    # def _onchange_waste_type_id_disposal_site(self):
    #
    #     self.disposal_site_id = False
    #
    #     if not self.waste_type_id:
    #         return
    #
    #     waste_name = (self.waste_type_id.name or '').strip().lower()
    #
    #     allowed_type = False
    #
    #     if waste_name == 'hazardous':
    #         allowed_type = 'hazardous'
    #
    #     elif waste_name == 'general compactable':
    #         allowed_type = 'general_compactable'
    #
    #     elif waste_name == 'general non-compactable':
    #         allowed_type = 'general_non-compactable'
    #
    #     if (
    #             self.disposal_site_id
    #             and self.disposal_site_id.waste_type != allowed_type
    #     ):
    #         self.disposal_site_id = False

    @api.depends('waste_type_id', 'pickup_point_ids', 'partner_id', 'disposal_site_id')
    def _compute_disposal_site_geo(self):
        """Rank licensed disposal sites and build map data without live geocoding."""
        DisposalSite = self.env['waste.disposal.site']
        geo = self.env['wmz.geo.mixin']

        for rec in self:
            waste_code = DisposalSite._waste_type_code_from_manifest(rec.waste_type_id)
            if waste_code:
                sites = DisposalSite.search(DisposalSite._domain_for_waste_type(waste_code))
            else:
                sites = DisposalSite.search([])

            location = rec.get_pickup_job_location(geocode=False)
            job_lat = location.get('lat')
            job_lon = location.get('lon')

            ranked = []
            if job_lat and job_lon and sites:
                ranked = DisposalSite.find_nearest_sites(
                    job_lat=job_lat,
                    job_lon=job_lon,
                    waste_type_code=waste_code,
                    limit=10,
                    geocode_missing=False,
                )
                rec.allowed_disposal_site_ids = DisposalSite.browse([
                    row['site_id'] for row in ranked
                ])
            else:
                rec.allowed_disposal_site_ids = sites

            site = rec.disposal_site_id
            if site and site.latitude and site.longitude and job_lat and job_lon:
                rec.disposal_site_distance_km = round(
                    geo.haversine_km(job_lat, job_lon, site.latitude, site.longitude),
                    2,
                )
            else:
                rec.disposal_site_distance_km = 0.0

            job = {
                'lat': job_lat or 0,
                'lon': job_lon or 0,
                'label': (
                    location.get('full_address')
                    or location.get('pickup_point_name')
                    or 'Pickup point'
                ),
            }
            providers = []
            summary_lines = []
            for idx, row in enumerate(ranked, start=1):
                site_rec = row['site']
                label = site_rec.site_code or site_rec.name or 'Disposal site'
                providers.append({
                    'id': site_rec.id,
                    'name': label,
                    'address': site_rec.full_address or '',
                    'lat': site_rec.latitude,
                    'lon': site_rec.longitude,
                    'distance_km': row['distance_km'],
                    'rank': idx,
                    'city': '',
                })
                summary_lines.append(f"#{idx} {label} — {row['distance_km']} km")

            if job_lat or providers:
                rec.disposal_map_data_json = json.dumps({'job': job, 'providers': providers})
            else:
                rec.disposal_map_data_json = ''
            rec.nearest_disposal_sites_summary = '\n'.join(summary_lines)

    @api.onchange('pickup_point_ids', 'waste_type_id', 'partner_id')
    def _onchange_suggest_nearest_disposal_site(self):
        """Pre-select the closest licensed site when pickup location or waste type changes."""
        if self.disposal_site_id:
            return
        if self.allowed_disposal_site_ids:
            self.disposal_site_id = self.allowed_disposal_site_ids[0]


    @api.onchange('waste_type_id')
    def _onchange_waste_type_id_disposal_site(self):

        if not self.disposal_site_id:
            return

        waste_name = (self.waste_type_id.name or '').strip().lower()

        allowed_type = False

        if waste_name == 'hazardous':
            allowed_type = 'hazardous'

        elif waste_name == 'general compactable':
            allowed_type = 'general_compactable'

        elif waste_name == 'general non-compactable':
            allowed_type = 'general_non-compactable'

        # Allow empty disposal site waste type everywhere
        if self.disposal_site_id.waste_type in (False, allowed_type):
            return

        self.disposal_site_id = False

        # @api.onchange('waste_type_id')
        # def _onchange_waste_type_id_disposal_site(self):
        #
        #     if not self.disposal_site_ids:
        #         return
        #
        #     waste_name = (self.waste_type_id.name or '').strip().lower()
        #
        #     allowed_type = False
        #
        #     if waste_name == 'hazardous':
        #         allowed_type = 'hazardous'
        #
        #     elif waste_name == 'general compactable':
        #         allowed_type = 'general_compactable'
        #
        #     elif waste_name == 'general non-compactable':
        #         allowed_type = 'general_non-compactable'
        #
        #     allowed_sites = self.disposal_site_ids.filtered(
        #         lambda s:
        #         not s.waste_type
        #         or s.waste_type == allowed_type
        #     )
        #
        #     self.disposal_site_ids = allowed_sites



    _BUSY_EXCLUDE_STATES = ('cancelled', 'draft', 'none')

    @api.model
    def _busy_until_planned_date_domain(self, exclude_request_id=None, company_id=None):
        """Manifests that still block fleet resources.

        A driver/truck is busy while the current time is *before* the manifest
        planned datetime. Once planned datetime has passed, the resource is free.
        Any active manifest with a future planned date counts, including Generated.
        """
        now = fields.Datetime.now()
        domain = [
            ('planned_date', '>', now),
            ('planned_date', '!=', False),
            ('state', 'not in', list(self._BUSY_EXCLUDE_STATES)),
        ]
        if exclude_request_id:
            domain.append(('id', '!=', exclude_request_id))
        if company_id:
            domain.append(('company_id', '=', company_id))
        return domain

    @api.model
    def _get_busy_resource_ids(self, resource_field, exclude_request_id=None, company_id=None):
        """Return IDs for drivers/assistants/vehicles still busy on other manifests."""
        domain = self._busy_until_planned_date_domain(
            exclude_request_id=exclude_request_id,
            company_id=company_id,
        )
        domain.append((resource_field, '!=', False))
        return self.sudo().search(domain).mapped(resource_field).ids

    @api.model
    def _get_busy_drivers_at_date(self, at_datetime, company_id=None):
        """Return partner IDs of drivers still busy before their planned datetime."""
        if not at_datetime:
            return []
        domain = [
            ('planned_date', '>', at_datetime),
            ('planned_date', '!=', False),
            ('driver_id', '!=', False),
            ('state', 'not in', list(self._BUSY_EXCLUDE_STATES)),
        ]
        if company_id:
            domain.append(('company_id', '=', company_id))
        return self.sudo().search(domain).mapped('driver_id').ids

    @api.model
    def _get_busy_assistants_at_date(self, at_datetime, company_id=None):
        if not at_datetime:
            return []
        domain = [
            ('planned_date', '>', at_datetime),
            ('planned_date', '!=', False),
            ('assistance_id', '!=', False),
            ('state', 'not in', list(self._BUSY_EXCLUDE_STATES)),
        ]
        if company_id:
            domain.append(('company_id', '=', company_id))
        return self.sudo().search(domain).mapped('assistance_id').ids


    busy_driver_ids = fields.Many2many(
        'res.partner',
        'waste_service_request_busy_driver_rel',
        'request_id',
        'employee_id',
        compute="_compute_busy_drivers",
        store=False,  # <-- changed from True
        string="Busy Drivers"
    )

    busy_assistance_ids = fields.Many2many(
        'res.partner',
        'waste_service_request_busy_assist_rel',
        'request_id',
        'employee_id',
        compute="_compute_busy_assistants",
        store=False,  # <-- changed
        string="Busy Assistants"
    )

    busy_track_ids = fields.Many2many(
        'fleet.vehicle',
        'waste_service_request_busy_truck_rel',
        'request_id',
        'vehicle_id',
        compute="_compute_busy_trucks",
        store=False,  # <-- changed
        string="Busy Trucks"
    )

    busy_trailler_ids = fields.Many2many(
        'fleet.vehicle',
        'waste_service_request_busy_trailer_rel',
        'request_id',
        'vehicle_id',
        compute="_compute_busy_traillers",
        store=False,  # <-- changed
        string="Busy Trailers"
    )

    # Checkbox (optional – if you already have it, keep yours)
    is_service_provider = fields.Boolean(string='Use Service Provider?')

    # Selected service provider
    provider_id = fields.Many2one('wms.service.provider', string="Service Provider")

    provider_name = fields.Char(
        string="Name",
        related='provider_id.name',
        store=True,
        readonly=True,
    )
    provider_full_address = fields.Text(
        string="Location",
        related='provider_id.full_address',
        readonly=True,
    )
    provider_province = fields.Selection(
        SA_PROVINCES,
        string="Province",
        related='provider_id.province',
        store=True,
        readonly=True,
    )
    provider_city = fields.Char(
        string="City",
        related='provider_id.city',
        store=True,
        readonly=True,
    )
    provider_suburb = fields.Char(
        string="Suburb",
        related='provider_id.suburb',
        store=True,
        readonly=True,
    )
    provider_phone = fields.Char(
        string="Phone",
        related='provider_id.phone',
        readonly=True,
    )
    provider_mobile = fields.Char(
        string="Mobile",
        related='provider_id.mobile',
        readonly=True,
    )
    provider_email = fields.Char(
        string="Email",
        related='provider_id.email',
        readonly=True,
    )
    provider_distance_km = fields.Float(
        string="Provider Distance (km)",
        readonly=True,
        copy=False,
    )




    def get_pickup_job_location(self, geocode=False):
        """Resolve job-site coordinates from the first pickup point's customer address.

        :param geocode: when False (default), use stored partner coordinates only —
            avoids slow Nominatim calls on form load. Set True for wizard search actions.
        """
        self.ensure_one()
        geo = self.env["wmz.geo.mixin"]
        pickup = self.pickup_point_ids[:1]
        partner = pickup.partner_id if pickup else self.partner_id
        if not partner:
            return {
                "lat": False,
                "lon": False,
                "full_address": "",
                "display_name": "",
                "province": False,
                "city": "",
                "suburb": "",
                "pickup_point_name": pickup.name if pickup else "",
            }

        full_address = geo.format_partner_address(partner)
        state_code = partner.state_id.code if partner.state_id else False
        province = state_code if state_code in dict(SA_PROVINCES) else False
        city = geo._clean_address_part(partner.city)
        suburb = geo._clean_address_part(partner.street2)

        lat, lon = False, False
        components = {}
        if partner.partner_latitude and partner.partner_longitude:
            lat = partner.partner_latitude
            lon = partner.partner_longitude
        elif geocode and full_address:
            result = geo.geocode_query(full_address)
            lat = result.get("lat")
            lon = result.get("lon")
            components = result.get("components") or {}
            if lat and lon:
                partner.sudo().write({
                    'partner_latitude': lat,
                    'partner_longitude': lon,
                })
            if not province and components.get("province"):
                province = components["province"]
            if not city and components.get("city"):
                city = components["city"]
            if not suburb and components.get("suburb"):
                suburb = components["suburb"]

        return {
            "lat": lat,
            "lon": lon,
            "full_address": full_address,
            "display_name": full_address,
            "province": province,
            "city": city,
            "suburb": suburb,
            "pickup_point_name": pickup.name if pickup else "",
        }

    # ---------------------------------------------------------
    @api.onchange("is_service_provider")
    def _onchange_is_service_provider_clear_fields(self):
        """
        If service provider is used -> clear internal fleet assignment fields.
        If not -> clear provider fields.
        """
        for rec in self:
            if rec.is_service_provider:
                # Using service provider => clear fleet assignment
                rec.vehicle_id = False
                rec.trailer_id = False
                # driver_id + assistance_id are related to vehicle_id -> will clear automatically
            else:
                # Not using service provider => clear provider selection
                rec.provider_id = False
                # related provider_* fields will clear automatically because they are related to provider_id

    # ---------------------------------------------------------
    # Service provider wizard.
    # ---------------------------------------------------------
    def action_open_simple_provider_wizard(self):
        """
        Open the provider-search wizard for this waste.service.request.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Find Service Provider',
            'res_model': 'waste.request.provider.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'waste.service.request',
                'active_id': self.id,
            },
        }

    def action_open_disposal_site_wizard(self):
        """Open the disposal-site search wizard for this manifest."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Find Disposal Site',
            'res_model': 'waste.request.disposal.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'waste.service.request',
                'active_id': self.id,
            },
        }

    # ---------------------------------------------------------
    # Busy Drivers and assistance depend on planned date.
    # Busy until planned datetime; free after it passes.
    # ---------------------------------------------------------
    @api.depends('planned_date', 'state', 'driver_id', 'vehicle_id', 'trailer_id', 'assistance_id', 'company_id')
    def _compute_busy_drivers(self):
        """Drivers assigned to other manifests still before their planned datetime."""
        for rec in self:
            exclude_id = rec._origin.id or rec.id or 0
            busy = rec._get_busy_resource_ids(
                'driver_id',
                exclude_request_id=exclude_id,
                company_id=rec.company_id.id,
            )
            rec.busy_driver_ids = [(6, 0, busy)]

    @api.depends('planned_date', 'state', 'driver_id', 'vehicle_id', 'trailer_id', 'assistance_id', 'company_id')
    def _compute_busy_assistants(self):
        """Assistants assigned to other manifests still before their planned datetime."""
        for rec in self:
            exclude_id = rec._origin.id or rec.id or 0
            busy = rec._get_busy_resource_ids(
                'assistance_id',
                exclude_request_id=exclude_id,
                company_id=rec.company_id.id,
            )
            rec.busy_assistance_ids = [(6, 0, busy)]

    @api.depends('planned_date', 'state', 'driver_id', 'vehicle_id', 'trailer_id', 'assistance_id', 'company_id')
    def _compute_busy_trucks(self):
        """Trucks assigned to other manifests still before their planned datetime."""
        for rec in self:
            exclude_id = rec._origin.id or rec.id or 0
            busy = rec._get_busy_resource_ids(
                'vehicle_id',
                exclude_request_id=exclude_id,
                company_id=rec.company_id.id,
            )
            rec.busy_track_ids = [(6, 0, busy)]

    @api.depends('planned_date', 'state', 'driver_id', 'vehicle_id', 'trailer_id', 'assistance_id', 'company_id')
    def _compute_busy_traillers(self):
        """Trailers assigned to other manifests still before their planned datetime."""
        for rec in self:
            exclude_id = rec._origin.id or rec.id or 0
            busy = rec._get_busy_resource_ids(
                'trailer_id',
                exclude_request_id=exclude_id,
                company_id=rec.company_id.id,
            )
            rec.busy_trailler_ids = [(6, 0, busy)]

    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('scheduled', 'Scheduled'),
        ('dispatched', 'Dispatched'),
        ('service_delivered', 'Service Delivered'),
        ('cancelled', 'Rejected'),
        ('done', 'Authorised'),
        ('none', 'None'),
    ], default='draft', tracking=True, group_expand='_read_group_expand_state')

    @api.model
    def _read_group_expand_state(self, states, domain, order):
        """Show all workflow columns in kanban, even when empty."""
        return [key for key, _label in self._fields['state'].selection if key != 'none']

    # ✅ new helper field for human label
    state_label = fields.Char(
        string="Status Label",
        compute="_compute_state_label",
        store=False,
    )

    @api.depends('state')
    def _compute_state_label(self):
        """Human-readable label for the current workflow state."""
        selection = dict(self._fields['state'].selection)
        for rec in self:
            rec.state_label = selection.get(rec.state, rec.state or '')

    # ---------------------------------------------------------
    # verification and validation of fields
    # ---------------------------------------------------------
    @api.constrains(
        "state",
        "planned_date",
        "driver_id",
        "vehicle_id",
        "wizard_pickup_point_ids",
        "is_service_provider",
        "pickup_point_ids",
        "provider_id",
    )
    def _check_required_fields_in_states(self):
        for rec in self:

            # Required when generated
            if rec.state == "generated":
                if not rec.pickup_point_ids:
                    raise ValidationError(_("Please Enter Pickup Point/ Drop Off Point 📍."))

            # Required when scheduled
            if rec.state == "scheduled":

                if not rec.planned_date:
                    raise ValidationError(_("Please Enter Manifest Planned Date ⌚."))

                if rec.is_service_provider and not rec.provider_id:
                    raise ValidationError(
                        _("Please select a service provider using the 'Find Service Provider' button.")
                    )

                # ✅ Internal job → vehicle and driver required
                if not rec.is_service_provider:
                    if not rec.vehicle_id:
                        raise ValidationError(
                            _("Please Enter Vehicle Registration Number 🚚.")
                        )
                    if not rec.driver_id:
                        raise ValidationError(
                            _("Please select a driver before scheduling.")
                        )

    @api.model
    def action_signature(self):
        """Open the driver signature capture wizard."""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Enter Signature',
            'res_model': 'driver.signature',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
            },
        }

    inUse = fields.Boolean(string='InUse', related='container_id.inUse', store=True)
    tank_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_tanks_rel',
        string="Tanks")

    pickup_point_ids = fields.Many2many(
        'pickup.point',
        'waste_request_pickup_point_rel',
        'request_id',
        'pickup_point_id',
        string="Pickup Points",
    )

    dropoff_point_ids = fields.Many2many(
        'pickup.point',
        'waste_request_dropoff_point_rel',
        'request_id',
        'pickup_point_id',
        string="Drop-off Points",
    )
    bin_lifted_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_bin_lifted_rel',  # relation table
        'request_id',  # FK to waste.service.request
        'waste_container_id',  # FK to waste.container (existing column)
        string="Bin Lifted",
    )

    bin_dropped_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_bin_dropped_rel',  # relation table
        'request_drop_id',  # FK to waste.service.request
        'waste_container_id',  # FK to waste.container (existing column)
        string="Bin Dropped",
    )

    ticket_type = fields.Selection(
        [
            ('pickup', 'Pickup'),
            ('followup', 'Follow-up'),
        ],
        string="Ticket Type",
        default='pickup',
        tracking=True,
    )

    # ---------------------------------------------------------
    # When customer changes, clear pickup/dropoff so user re-selects.
    # ---------------------------------------------------------
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """When customer changes, clear pickup/dropoff so user re-selects."""
        self.pickup_point_ids = False
        self.dropoff_point_ids = False

    # # ---------------------------------------------------------
    # # Check pickup point and Bins.
    # # ---------------------------------------------------------
    # @api.constrains('partner_id', 'pickup_point_ids', 'dropoff_point_ids', 'bin_lifted_ids')
    # def _check_pickup_points_and_bins(self):
    #     for rec in self:
    #         # If no customer, nothing to validate
    #         if not rec.partner_id:
    #             continue
    #
    #         # --------------------------------------------------
    #         # 1) Pickup points must belong to the same customer
    #         # --------------------------------------------------
    #
    #         for pp in rec.pickup_point_ids:
    #
    #             if pp.partner_id and pp.partner_id != rec.partner_id:
    #                 raise ValidationError(_(
    #                     "Pickup point '%(pp)s' belongs to customer '%(c_pp)s', "
    #                     "but this request is for customer '%(c_req)s'.",
    #                     pp=pp.display_name,
    #                     c_pp=pp.partner_id.display_name,
    #                     c_req=rec.partner_id.display_name,
    #                 ))
    #
    #         # --------------------------------------------------
    #         # 2) Drop-off points must also belong to same customer
    #         # --------------------------------------------------
    #         for pp in rec.dropoff_point_ids:
    #             if pp.partner_id and pp.partner_id != rec.partner_id:
    #                 raise ValidationError(_(
    #                     "Drop-off point '%(pp)s' belongs to customer '%(c_pp)s', "
    #                     "but this request is for customer '%(c_req)s'.",
    #                     pp=pp.display_name,
    #                     c_pp=pp.partner_id.display_name,
    #                     c_req=rec.partner_id.display_name,
    #                 ))
    #
    #         # --------------------------------------------------
    #         # 3) Bins must belong to the same customer AND
    #         #    be linked to one of the selected pickup points
    #         # --------------------------------------------------
    #         if not rec.pickup_point_ids or not rec.bin_lifted_ids:
    #             # No pickup points or no bins -> nothing more to validate
    #             continue
    #
    #         allowed_pp_ids = set(rec.pickup_point_ids.ids)
    #
    #
    #
    #         for cont in rec.bin_lifted_ids:
    #
    #             _logger.warning(
    #                 "BIN=%s PICKUP=%s ALLOWED=%s",
    #                 cont.display_name,
    #                 cont.pickup_point_id.display_name if cont.pickup_point_id else "None",
    #                 rec.pickup_point_ids.ids
    #             )
    #             # 3.1) Check bin's customer
    #             if cont.partner_id and cont.partner_id != rec.partner_id:
    #                 raise ValidationError(_(
    #                     "Bin %(bin)s belongs to customer %(c_bin)s, "
    #                     "but this request is for customer %(c_req)s.",
    #                     bin=cont.display_name,
    #                     c_bin=cont.partner_id.display_name,
    #                     c_req=rec.partner_id.display_name,
    #                 ))
    #
    #             # 3.2) Check bin's pickup point is in selected pickup points
    #             if cont.pickup_point_id and cont.pickup_point_id.id not in allowed_pp_ids:
    #                 raise ValidationError(_(
    #                     "Bin %(bin)s is linked to pickup point %(pp_bin)s, "
    #                     "which is not in the selected pickup points for this request.",
    #                     bin=cont.display_name,
    #                     pp_bin=cont.pickup_point_id.display_name,
    #                 ))


    condition = fields.Selection([
        ('draft', 'draft'),
        ('done', 'Done')],
        string='Condition', default='draft')

    liters_collected = fields.Float(
        string="Liters to Collect",
        compute="_compute_liters_from_qty",
        store=True,
        help="For Tank jobs: kL quantity × 1000."
    )

    # For info / debugging
    billing_kl = fields.Float(
        string="Billing kL",
        compute="_compute_billing_amount",
        store=True,
        help="Liters converted to kiloliters for billing."
    )

    billing_amount = fields.Float(
        string="Billing Amount (Excl. VAT)",
        compute="_compute_billing_amount",
        store=True,
        help="Calculated from liters using rate: 4 kL base + extra per kL."
    )

    truck_tanker_id = fields.Many2one('tank.volume', string="Track Tanker", related="vehicle_id.tank_volume_id",
                                      store=False)
    image_ids = fields.One2many(
        'waste.worksheet.image',
        'worksheet_id',
        string='Photos',
    )
    notes_html = fields.Html(
        related="work_sheet_id.notes_html",
        string="Worksheet Notes",
        store=False,  # or True if you want it stored/searchable
        readonly=False,  # set False if you want to edit from manifest
        help="Add notes and embed pictures directly in the content.",
    )

    @api.depends('product_uom_qty', 'container_type_id')
    def _compute_liters_from_qty(self):
        """Derive liters collected from kL quantity on tank jobs."""
        for rec in self:
            if rec._is_tank_job():
                # kL → L
                rec.liters_collected = (rec.product_uom_qty or 0.0) * 1000.0
            else:
                # For non-tank jobs you can keep it 0 or leave manual if you want
                rec.liters_collected = rec.liters_collected or 0.0


    qty_updated_from_worksheet = fields.Boolean(
        string="Quantity Updated from Worksheet",
        default=False,
        tracking=True,
        help="Ticked automatically when the driver updates quantity from the worksheet.",
    )

    qty_update_label = fields.Char(
        string="",
        compute="_compute_qty_update_label",
        store=False,
    )

    @api.depends('qty_updated_from_worksheet')
    def _compute_qty_update_label(self):
        """Show a label when quantity was updated from the worksheet."""
        for rec in self:
            rec.qty_update_label = _("Updated from worksheet") if rec.qty_updated_from_worksheet else False

    # ---------------------------------------------------------
    # Tank rates
    # ---------------------------------------------------------
    def _get_rate_params(self):
        """
        Decide which rate table to use based on waste details.
        Tariffs are configured in waste.tank.tariff.
        """

        def norm(txt):
            return (txt or "").strip().lower()

        wd_name = norm(self.waste_details_id.name)

        Tariff = self.env["waste.tank.tariff"].sudo()

        # Default: Septic
        tariff = Tariff.search([
            ("code", "=", "septic"),
            ("active", "=", True)
        ], limit=1)

        # Grease detection
        if "grease" in wd_name:
            grease = Tariff.search([
                ("code", "=", "grease"),
                ("active", "=", True)
            ], limit=1)
            tariff = grease or tariff

        if not tariff:
            raise ValidationError(_("No tank tariff configured."))

        return tariff.base_kl, tariff.base_price, tariff.extra_rate

    @api.depends('product_uom_qty', 'waste_type_id', 'container_type_id')
    def _compute_billing_amount(self):
        """Calculate tank billing kL and amount from configured tariffs."""
        for rec in self:
            # Only apply this logic to Tank jobs
            if not rec._is_tank_job():
                rec.billing_kl = 0.0
                rec.billing_amount = 0.0
                continue

            kl = rec.product_uom_qty or 0.0  # 🔹 quantity = kL
            if kl <= 0.0:
                rec.billing_kl = 0.0
                rec.billing_amount = 0.0
                continue

            base_kl, base_price, extra_rate = rec._get_rate_params()

            if kl <= base_kl:
                amount = base_price
            else:
                extra_kl = kl - base_kl
                amount = base_price + extra_kl * extra_rate

            rec.billing_kl = kl
            rec.billing_amount = amount

    # ===============================Tanks Helpers=======================
    def _is_tank_job(self):
        ctype = (self.container_type_id.name or "").strip().lower()
        return ctype == "tank"

    def _post_tank_summary_message(self):
        """
        Post a nice summary in the chatter for Tank jobs
        whenever the record is saved.
        """
        for rec in self:
            if not rec._is_tank_job():
                continue

            # need some volume and amount to say anything useful
            if not rec.billing_kl or rec.billing_kl <= 0:
                continue

            liters = rec.liters_collected or (rec.billing_kl * 1000.0)
            base_kl, base_price, extra_rate = rec._get_rate_params()

            # Try to show a friendly service name
            service_label = (
                    rec.waste_type_id.display_name
                    or rec.service_requested_id.display_name
                    or _("Tank Service")
            )

            so_part = (
                _("Linked SO: %s") % rec.sale_order_id.name
                if rec.sale_order_id
                else _("No Sales Order linked yet")
            )

            body = _(
                "Tank job summary:"
                "- Service: %(service)s"
                "- Quantity: %(kl).2f kL (%(liters).0f L)"
                "- Tariff: first %(base_kl).0f kL at R%(base_price).2f, "
                "extra kL at R%(extra_rate).2f"
                "- Calculated amount (excl. VAT): R%(amount).2f"
                "- %(so)s",
                service=service_label,
                kl=rec.billing_kl,
                liters=liters,
                base_kl=base_kl,
                base_price=base_price,
                extra_rate=extra_rate,
                amount=rec.billing_amount or 0.0,
                so=so_part,
            )

            rec.message_post(body=body)

        # these are just related helpers for the domain

    sale_order_id = fields.Many2one('sale.order', string="Sales Order")
    sale_order_name = fields.Char(
        related='sale_order_id.name',
        string='Sales Order Number',
        readonly=True,
    )

    # ------------------------------------------------------------
    # Force company (internal forms)
    # ------------------------------------------------------------
    @api.onchange()
    def _onchange_force_company(self):
        self.company_id = self.env.company

    # ------------------------------------------------------------
    # Allowed M2M (for domains + validation)
    # ------------------------------------------------------------
    allowed_service_ids = fields.Many2many(
        "service.request", compute="_compute_allowed_configs", compute_sudo=True, store=False
    )
    allowed_container_type_ids = fields.Many2many(
        "container.type", compute="_compute_allowed_configs", compute_sudo=True, store=False
    )
    allowed_waste_type_ids = fields.Many2many(
        "waste.type", compute="_compute_allowed_configs", compute_sudo=True, store=False
    )
    allowed_waste_details_ids = fields.Many2many(
        "waste.details", compute="_compute_allowed_configs", compute_sudo=True, store=False
    )
    allowed_bin_type_ids = fields.Many2many(
        "bin.type", compute="_compute_allowed_configs", compute_sudo=True, store=False
    )
    allowed_tank_volume_ids = fields.Many2many(
        "tank.volume", compute="_compute_allowed_configs", compute_sudo=True, store=False
    )

    # ------------------------------------------------------------
    # Fields with domains (SAFE)
    # ------------------------------------------------------------
    service_requested_id = fields.Many2one(
        "service.request", domain="[('id','in', allowed_service_ids)]"
    )
    container_type_id = fields.Many2one(
        "container.type", domain="[('id','in', allowed_container_type_ids)]"
    )
    waste_type_id = fields.Many2one(
        "waste.type", domain="[('id','in', allowed_waste_type_ids)]"
    )
    waste_details_id = fields.Many2one(
        "waste.details", domain="[('id','in', allowed_waste_details_ids)]"
    )
    bin_type_id = fields.Many2one(
        "bin.type", domain="[('id','in', allowed_bin_type_ids)]"
    )
    tank_volume_id = fields.Many2one(
        "tank.volume", domain="[('id','in', allowed_tank_volume_ids)]"
    )

    # ------------------------------------------------------------
    # Core logic — NEVER returns empty lists
    # ------------------------------------------------------------
    @api.depends("company_id")
    def _compute_allowed_configs(self):
        """Restrict service/config pickers to company-allowed master data."""
        Service = self.env["service.request"].sudo()
        Container = self.env["container.type"].sudo()
        Waste = self.env["waste.type"].sudo()
        WasteDetails = self.env["waste.details"].sudo()
        Bin = self.env["bin.type"].sudo()
        Tank = self.env["tank.volume"].sudo()

        for rec in self:
            company = (rec.company_id or rec.env.company).sudo()

            rec.allowed_service_ids = company.wmz_service_ids or Service.search([])
            rec.allowed_container_type_ids = company.wmz_container_type_ids or Container.search([])
            rec.allowed_waste_type_ids = company.wmz_waste_type_ids or Waste.search([])
            rec.allowed_waste_details_ids = (
                company.wmz_waste_details_ids
                if "wmz_waste_details_ids" in company._fields and company.wmz_waste_details_ids
                else WasteDetails.search([])
            )
            rec.allowed_bin_type_ids = company.wmz_bin_type_ids or Bin.search([])
            rec.allowed_tank_volume_ids = company.wmz_tank_volume_ids or Tank.search([])

    # ------------------------------------------------------------
    # Hard validation (SAVE-time safety)
    # ------------------------------------------------------------
    @api.constrains(
        "service_requested_id",
        "container_type_id",
        "waste_type_id",
        "waste_details_id",
        "bin_type_id",
        "tank_volume_id",
    )
    def _check_allowed_config(self):
        for rec in self:
            if rec.service_requested_id not in rec.allowed_service_ids:
                raise ValidationError(_("Selected service is not allowed for this company."))
            if rec.container_type_id not in rec.allowed_container_type_ids:
                raise ValidationError(_("Selected container type is not allowed for this company."))
            if rec.waste_type_id not in rec.allowed_waste_type_ids:
                raise ValidationError(_("Selected waste type is not allowed for this company."))
            if rec.waste_details_id and rec.waste_details_id not in rec.allowed_waste_details_ids:
                raise ValidationError(_("Selected waste detail is not allowed for this company."))
            if rec.bin_type_id and rec.bin_type_id not in rec.allowed_bin_type_ids:
                raise ValidationError(_("Selected bin type is not allowed for this company."))
            if rec.tank_volume_id and rec.tank_volume_id not in rec.allowed_tank_volume_ids:
                raise ValidationError(_("Selected tank volume is not allowed for this company."))

    # ------------------------------------------------------------
    # Counts (UI / smart buttons / debug)
    # ------------------------------------------------------------
    allowed_service_count = fields.Integer(compute="_compute_allowed_counts", store=False)
    allowed_container_count = fields.Integer(compute="_compute_allowed_counts", store=False)
    allowed_waste_count = fields.Integer(compute="_compute_allowed_counts", store=False)

    def _compute_allowed_counts(self):
        """Count allowed services, containers, and waste types for UI hints."""
        for rec in self:
            rec.allowed_service_count = len(rec.allowed_service_ids)
            rec.allowed_container_count = len(rec.allowed_container_type_ids)
            rec.allowed_waste_count = len(rec.allowed_waste_type_ids)

    hide_waste_type = fields.Boolean(compute='_compute_field_visibility')
    hide_waste_details = fields.Boolean(compute='_compute_field_visibility')
    hide_droppoff_container_ids_placement = fields.Boolean(compute='_compute_field_visibility')
    hide_droppoff_container_ids_removal = fields.Boolean(compute='_compute_field_visibility')
    hide_droppoff_container_ids_collection = fields.Boolean(compute='_compute_field_visibility')
    hide_droppoff_container_ids_is_bin = fields.Boolean(compute='_compute_field_visibility')
    hide_lifted_bin_ids_swap = fields.Boolean(compute='_compute_field_visibility')
    hide_dropped_bin_ids_swap = fields.Boolean(compute='_compute_field_visibility')
    hide_dropped_to_swap = fields.Boolean(compute='_compute_field_visibility')
    hide_shunt_container_ids = fields.Boolean(compute='_compute_field_visibility')
    hide_shunt_to_id = fields.Boolean(compute='_compute_field_visibility')
    hide_tank_ids = fields.Boolean(compute='_compute_field_visibility')
    hide_tank_volume = fields.Boolean(compute='_compute_field_visibility')
    hide_liters_collected = fields.Boolean(compute='_compute_field_visibility')
    hide_liters_remaining = fields.Boolean(compute='_compute_field_visibility')
    hide_service_collection = fields.Boolean(compute='_compute_field_visibility')
    hide_tank = fields.Boolean(compute='_compute_field_visibility')
    hide_bin = fields.Boolean(compute='_compute_field_visibility')
    hide_hazardous_fields = fields.Boolean(compute='_compute_field_visibility')
    hide_general = fields.Boolean(compute='_compute_field_visibility')
    hide_none_general = fields.Boolean(compute='_compute_field_visibility')
    hide_service_placement = fields.Boolean(compute='_compute_field_visibility')
    hide_disposal_site = fields.Boolean(compute='_compute_field_visibility')
    hide_pickup_point = fields.Boolean(compute='_compute_field_visibility')

    # ---------------------------------------------------------
    # FIELDS VISIBILITY
    # ---------------------------------------------------------
    @api.depends('service_requested_id', 'container_type_id', 'waste_type_id',
                 'service_requested_id.name', 'container_type_id.name', 'waste_type_id.name')
    def _compute_field_visibility(self):
        """Toggle form field visibility based on service and container type."""
        for rec in self:
            is_waste_type = (rec.service_requested_id.name or '').strip().lower()
            is_waste_details = (rec.service_requested_id.name or '').strip().lower()
            is_placement = (rec.service_requested_id.name or '').strip().lower()
            is_removal = (rec.service_requested_id.name or '').strip().lower()
            is_collection = (rec.service_requested_id.name or '').strip().lower()
            is_container = (rec.container_type_id.name or '').strip().lower()
            is_swap_lifted_bin = (rec.service_requested_id.name or '').strip().lower()
            is_swap_dropped_bin = (rec.service_requested_id.name or '').strip().lower()
            is_swap_dropped_to = (rec.service_requested_id.name or '').strip().lower()
            is_shunt_container_ids = (rec.service_requested_id.name or '').strip().lower()
            is_shunt_to_id = (rec.service_requested_id.name or '').strip().lower()
            is_tank_ids = (rec.container_type_id.name or '').strip().lower()
            is_tank_volume = (rec.container_type_id.name or '').strip().lower()
            is_litters_collected = (rec.container_type_id.name or '').strip().lower()
            is_letter_remaining = (rec.container_type_id.name or '').strip().lower()
            is_service_collection = (rec.service_requested_id.name or '').strip().lower()
            is_tank = (rec.container_type_id.name or '').strip().lower()
            is_bin = (rec.container_type_id.name or '').strip().lower()
            is_hazardous = (rec.waste_type_id.name or '').strip().lower()
            is_general = (rec.waste_type_id.name or '').strip().lower()
            is_none_general = (rec.waste_type_id.name or '').strip().lower()
            is_disposal_site = (rec.waste_type_id.name or '').strip().lower()
            is_service_placement = (rec.service_requested_id.name or '').strip().lower()
            is_pickup_point = (rec.service_requested_id.name or '').strip().lower()

            rec.hide_waste_type = (is_waste_type == 'placement of bins')
            rec.hide_waste_details = (is_waste_details == 'placement of bins')
            rec.hide_droppoff_container_ids_placement = (is_placement == 'placement of bins')
            rec.hide_droppoff_container_ids_removal = (is_removal == 'removal of bins')
            rec.hide_droppoff_container_ids_collection = (is_collection == 'waste collection & disposal')
            rec.hide_droppoff_container_ids_is_bin = (is_container == 'bin')
            rec.hide_lifted_bin_ids_swap = (is_swap_lifted_bin == 'swapping of bins')
            rec.hide_dropped_bin_ids_swap = (is_swap_dropped_bin == 'swapping of bins')
            rec.hide_dropped_to_swap = (is_swap_dropped_to == 'swapping of bins')
            rec.hide_shunt_container_ids = (is_shunt_container_ids == 'shunting of bins')
            rec.hide_shunt_to_id = (is_shunt_to_id == 'shunting of bins')
            rec.hide_tank_ids = (is_tank_ids == 'tank')
            rec.hide_tank_volume = (is_tank_volume == 'tank')
            rec.hide_liters_collected = (is_litters_collected == 'tank')
            rec.hide_liters_remaining = (is_letter_remaining == 'tank')
            rec.hide_service_collection = (is_service_collection == 'waste collection & disposal')
            rec.hide_tank = (is_tank == 'tank')
            rec.hide_bin = (is_bin == 'bin')
            rec.hide_hazardous_fields = (is_hazardous == 'hazardous')
            rec.hide_general = (is_general == 'general compactable')
            rec.hide_none_general = (is_none_general == 'general non compactable')
            rec.hide_disposal_site = (is_disposal_site == 'hazardous')
            rec.hide_service_placement = (is_service_placement == 'placement of bins')
            rec.hide_pickup_point = (is_pickup_point == 'placement of bins')

    # sale_order_id = fields.Many2one('sale.order', string="Sales Order")
    product_id = fields.Many2one('product.product', string="Product")
    # product_uom_qty = fields.Float(string="Quantity")
    price_unit = fields.Float(string="Unit Price")

    order_line_id = fields.Many2one(
        'sale.order.line',
        string="Sale Order Line",
        ondelete='set null',
        help="The sale order line that this service request should update."
    )


    # REPLACE your old product_uom_qty field with this one
    product_uom_qty = fields.Float(
        string="Quantity",
        compute="_compute_product_uom_qty",
        store=True,
        tracking=True,
        readonly=False,  # still editable if you want
    )

    # ---------------------------------------------------------
    # Remove extra Tank kL line without breaking confirmed SO rules.
    # ---------------------------------------------------------
    def _remove_extra_line_safely(self, so, extra_line):
        """Remove extra Tank kL line without breaking confirmed SO rules."""
        if not extra_line:
            return

        # If order is still editable, we can delete
        if so.state in ('draft', 'sent'):
            extra_line.unlink()
        else:
            # Confirmed order: set qty & price to 0 instead of deleting
            extra_line.with_context(skip_waste_sync=True).write({
                'product_uom_qty': 0.0,
                'price_unit': 0.0,
            })

    # ---------------------------------------------------------
    # QTY VISIBILITY
    # ---------------------------------------------------------
    @api.depends(
        "service_requested_id",
        "bin_lifted_ids",
        "bin_dropped_ids",
        "container_type_id",
    )
    def _compute_product_uom_qty(self):
        """
        For BIN jobs: compute qty from bins.
        For TANK jobs: do NOT override qty (user/SO sets kL quantity).
        """
        for rec in self:
            # 🔹 Skip Tank jobs – let user / SO control kL
            if rec._is_tank_job():
                continue

            svc_code = (rec.service_requested_id.code or "").lower() \
                if rec.service_requested_id and hasattr(rec.service_requested_id, "code") \
                else (rec.service_requested_id.display_name or "").strip().lower()

            # If no bins at all, don't override
            if not rec.bin_lifted_ids and not rec.bin_dropped_ids:
                rec.product_uom_qty = rec.product_uom_qty or 0.0
                continue

            qty = 0.0

            if svc_code == "placement of bins":
                qty = float(len(rec.bin_dropped_ids))

            elif svc_code in ("shunting of bins", "removal of bins"):
                qty = float(len(rec.bin_lifted_ids))

            elif svc_code == "waste collection & disposal":
                if rec.bin_lifted_ids:
                    qty = float(len(rec.bin_lifted_ids))
                elif rec.bin_dropped_ids:
                    qty = float(len(rec.bin_dropped_ids))

            elif svc_code == "swapping of bins":
                if rec.bin_lifted_ids:
                    qty = float(len(rec.bin_lifted_ids))
                elif rec.bin_dropped_ids:
                    qty = float(len(rec.bin_dropped_ids))

            rec.product_uom_qty = qty



    # ------------------------------------------------------------
    # SALE ORDER QTY SYNC
    # ------------------------------------------------------------
    def _sync_sale_order_qty(self):
        """
        Push current request qty to the related sale order line.
        Uses best matching line if order_line_id not set.

        BIN jobs:
            - Single SO line, qty = number of bins.

        TANK jobs:
            - Base line: fixed 4 kL @ base_price (qty = 1).
            - Extra line: extra kL @ extra_rate (qty = extra_kL).
        """
        for rec in self:
            so = rec.sale_order_id
            if not so:
                continue

            # 1) Use explicitly linked line if present
            line = rec.order_line_id
            if line and line.order_id != so:
                line = False

            # 2) Try to find a line linked by custom field (if you later add one)
            if not line and 'waste_request_id' in so.order_line._fields:
                line = so.order_line.filtered(lambda l: l.waste_request_id.id == rec.id)[:1]

            # 3) Try to match by service_requested_id if line has that field
            if not line and rec.service_requested_id and 'service_requested_id' in so.order_line._fields:
                line = so.order_line.filtered(
                    lambda l: l.service_requested_id.id == rec.service_requested_id.id
                )[:1]

            # 4) Fallback: first order line (keeps system working even without config)
            if not line:
                line = so.order_line[:1]

            if not line:
                # No line at all, nothing to sync
                continue

            # --------------------------------------------------------
            # TANK JOB → base line + extra kL line
            # --------------------------------------------------------
            if rec._is_tank_job():
                # kL for billing – prefer explicit qty, else computed billing_kl, else from liters
                kl = rec.product_uom_qty or rec.billing_kl or (
                    (rec.liters_collected / 1000.0) if rec.liters_collected else 0.0
                )

                base_kl, base_price, extra_rate = rec._get_rate_params()

                # Find existing extra line if any
                extra_line = so.order_line.filtered(
                    lambda l: 'Extra Tank kL' in (l.name or '') or
                              'Extra tanker kL' in (l.name or '')
                )[:1]

                if kl <= 0.0:
                    # Nothing to bill → zero base line and clear extra line safely
                    line.with_context(skip_waste_sync=True).write({
                        'product_uom_qty': 0.0,
                        'price_unit': 0.0,
                    })

                    rec._remove_extra_line_safely(so, extra_line)
                    rec.order_line_id = line
                    continue

                # How many kL are "extra" above base_kl
                extra_kl = max(0.0, kl - base_kl)

                # ---------- BASE LINE ----------
                base_name = line.product_id.display_name or line.name or _("Transport Rate (Tank)")
                base_suffix = f" – Base up to {base_kl:g} kL"
                base_line_vals = {
                    'product_uom_qty': 1.0,
                    'price_unit': base_price,
                    'name': base_name + base_suffix,
                }
                line.with_context(skip_waste_sync=True).write(base_line_vals)

                # ---------- EXTRA kL LINE ----------
                if extra_kl > 0:
                    extra_name = f"Extra Tank kL ({extra_kl:.2f} kL)"

                    if extra_line:
                        # Update existing extra line
                        extra_line.with_context(skip_waste_sync=True).write({
                            'product_uom_qty': extra_kl,
                            'price_unit': extra_rate,
                            'name': extra_name,
                        })
                    else:
                        # Create new extra line
                        rec.env['sale.order.line'].with_context(skip_waste_sync=True).create({
                            'order_id': so.id,
                            'product_id': line.product_id.id or rec.product_id.id,
                            'name': extra_name,
                            'product_uom_qty': extra_kl,
                            'price_unit': extra_rate,
                        })
                else:
                    # No extra kL → remove / neutralise extra line safely
                    rec._remove_extra_line_safely(so, extra_line)

                rec.order_line_id = line
                continue  # go to next rec

            # --------------------------------------------------------
            # NORMAL BIN JOB: keep existing qty-only sync
            # --------------------------------------------------------
           # sync qty = rec.product_uom_qty or 0.0
           #  line.with_context(skip_waste_sync=True).write({
           #      'product_uom_qty': qty
           #  })

            rec.order_line_id = line

    # ---------------------------------------------------------
    # Create and Write method
    # ---------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user
        current_company = user.company_id

        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            # Sequence
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'waste.service.request'
                ) or 'New'

            # Force company_id from USER company (portal or internal)
            # if not vals.get('company_id'):
            #     vals['company_id'] = current_company.id
            # for vals in vals_list:

            # If using service provider => force-clear fleet fields
            if vals.get("is_service_provider") is True:
                vals.update({
                    "vehicle_id": False,
                    "trailer_id": False,
                })
            # If NOT using service provider => force-clear provider fields
            if vals.get("is_service_provider") is False:
                vals.update({
                    "provider_id": False,
                })

        recs = super(
            WasteServiceRequest,
            self.with_company(current_company.id)
        ).create(vals_list)

        # Link SO etc...
        for rec in recs:
            if rec.sale_order_id:
                rec.sale_order_id.service_request_id = rec.id

        recs._sync_sale_order_qty()
        recs._post_tank_summary_message()

        return recs

    def write(self, vals):
        # If quantity is changed, decide if it came from worksheet
        if 'product_uom_qty' in vals and 'qty_updated_from_worksheet' not in vals:
            from_ws = self.env.context.get('from_worksheet', False)
            # If from worksheet → True, if from anywhere else (manifest) → False
            vals['qty_updated_from_worksheet'] = bool(from_ws)

        res = super().write(vals)

        # Keep driver + sale order links synced after updates
        for rec in self:
            # if rec.driver_id:
            #     rec.driver_id.service_request_id = rec.id
            if rec.sale_order_id:
                rec.sale_order_id.service_request_id = rec.id

        if any(k in vals for k in [
            'product_uom_qty',
            'service_requested_id',
            'bin_lifted_ids',
            'bin_dropped_ids',
            'liters_collected',
            'container_type_id',
            'waste_type_id',
        ]):
            to_sync = self.filtered(
                lambda r: not r.work_sheet_id or r.work_sheet_id.state == 'done'
            )
            to_sync._sync_sale_order_qty()

            # 🔹 Also post/update tank summary
            self._post_tank_summary_message()

        # If toggle happens, enforce clearing regardless of where write came from
        if "is_service_provider" in vals:
            if vals.get("is_service_provider") is True:
                # Using service provider => clear fleet assignment
                vals.update({
                    "vehicle_id": False,
                    "trailer_id": False,
                })
            else:
                # Not using service provider => clear provider
                vals.update({
                    "provider_id": False,
                })

    # ---------------------------------------------------------
    # Sales order helper and on change Method
    # ---------------------------------------------------------
    def _normalize_attr(self, name):
        # Helper to normalize attribute names: lower + strip + collapse spaces
        name = (name or "").strip().lower()
        # replace multiple spaces with one
        name = " ".join(name.split())
        return name

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        for rec in self:
            so = rec.sale_order_id
            if not so or not so.order_line:
                _logger.info("WSR onchange: no sale_order or no order_line for %s", rec.name)
                continue

            # 👉 take first line for now (you can later improve selection logic)
            line = so.order_line[:1]
            _logger.info("WSR onchange: using SO %s / line %s / product %s",
                         so.name, line.id, line.product_id.display_name)

            # ------------------------------
            # Basic product info from SO line
            # ------------------------------
            rec.product_id = line.product_id.id
            rec.price_unit = line.price_unit

            # Only override qty from SO if there are NO bins yet
            if not (rec.bin_lifted_ids or rec.bin_dropped_ids):
                rec.product_uom_qty = line.product_uom_qty
                _logger.info("WSR onchange: setting product_uom_qty from SO = %s",
                             line.product_uom_qty)
            else:
                _logger.info("WSR onchange: bins already selected, keeping qty = %s",
                             rec.product_uom_qty)

            # ------------------------------
            # Clear previous mapping fields
            # ------------------------------
            rec.service_requested_id = False
            rec.waste_type_id = False
            rec.waste_details_id = False
            rec.bin_type_id = False
            rec.container_type_id = False
            rec.tank_volume_id = False
            # tank_volume_id is related -> do not set directly

            # ------------------------------
            # Map product attributes → config models
            # ------------------------------
            # NOTE: keys are *normalized* names
            attr_to_model_field = {
                'service requested': ('service.request', 'service_requested_id'),
                'waste type': ('waste.type', 'waste_type_id'),
                'waste details': ('waste.details', 'waste_details_id'),
                'bin type': ('bin.type', 'bin_type_id'),
                'container type': ('container.type', 'container_type_id'),
                'tank volume': ('tank.volume', 'tank_volume_id'),
            }

            # Log all PTAVs on the product
            for ptav in line.product_id.product_template_attribute_value_ids:
                _logger.info(
                    "WSR onchange: PTAV -> attr=%s / value=%s (id=%s)",
                    ptav.attribute_id.name, ptav.product_attribute_value_id.name,
                    ptav.product_attribute_value_id.id
                )

            for ptav in line.product_id.product_template_attribute_value_ids:
                raw_attr_name = ptav.attribute_id.name or ''
                attr_name = rec._normalize_attr(raw_attr_name)
                pav = ptav.product_attribute_value_id
                if not pav:
                    continue

                mapping = attr_to_model_field.get(attr_name)
                _logger.info("WSR onchange: normalized attr '%s' -> mapping %s",
                             attr_name, mapping)

                if not mapping:
                    # just log and skip unknown attributes
                    continue

                model_name, field_name = mapping
                Model = self.env[model_name]

                # 1) Try strict pav_id match
                config_rec = Model.search([('pav_id', '=', pav.id)], limit=1)
                _logger.info("WSR onchange: search %s by pav_id=%s -> %s",
                             model_name, pav.id, config_rec)

                # 2) Fallback by name if pav_id not set or not matching
                if not config_rec:
                    config_rec = Model.search([('name', '=', pav.name)], limit=1)
                    _logger.info("WSR onchange: fallback search %s by name=%s -> %s",
                                 model_name, pav.name, config_rec)

                if config_rec and not getattr(rec, field_name):
                    setattr(rec, field_name, config_rec.id)
                    _logger.info("WSR onchange: SET %s.%s = %s",
                                 rec, field_name, config_rec.id)
                else:
                    if not config_rec:
                        _logger.warning("WSR onchange: NO config record found for %s: pav=%s name=%s",
                                        model_name, pav.id, pav.name)

    # ---------------------------------------------------------
    # Documents upload
    # ---------------------------------------------------------
    manifest_document = fields.Binary("Manifests Document", attachment=True)
    manifest_document_filename = fields.Char()
    weighbridge_slip = fields.Binary("Weighbridge Slip", attachment=True)
    weighbridge_slip_filename = fields.Char()
    safety_certificate = fields.Binary("Safety Certificate", attachment=True)
    safety_certificate_filename = fields.Char()

    # ---------------------------------------------------------
    # Worksheet mirrors
    # ---------------------------------------------------------
    worksheet_ids = fields.One2many(
        "waste.worksheet", "service_request_id", string="Worksheet",
    )
    worksheet_count = fields.Integer(
        string="Worksheets",
        compute="_compute_worksheets_count",
    )
    latest_worksheet_arrival_time = fields.Datetime(
        string='Arrival Time', compute="_compute_latest_worksheet", store=True,
    )
    latest_worksheet_kilometers = fields.Integer(
        string='Kilometers', compute="_compute_latest_worksheet", store=True,
    )
    latest_worksheet_return_date = fields.Datetime(
        string='Return Date', compute="_compute_latest_worksheet", store=True,
    )
    latest_worksheet_unit_of_measure = fields.Many2one(
        'uom.uom', string='Units of Measure',
        compute="_compute_latest_worksheet", store=True,
    )
    latest_worksheet_driver_signature = fields.Binary(
        string="Signature", compute="_compute_latest_worksheet", store=True,
    )
    latest_worksheet_manifest_document = fields.Binary(
        "Manifests Document", compute="_compute_latest_worksheet", store=True,
    )
    latest_worksheet_manifest_document_filename = fields.Char()
    latest_worksheet_weighbridge_slip = fields.Binary(
        "Weighbridge Slip", compute="_compute_latest_worksheet", store=True,
    )
    latest_worksheet_weighbridge_slip_filename = fields.Char()
    latest_worksheet_safety_certificate = fields.Binary(
        "Safety Certificate", compute="_compute_latest_worksheet", store=True,
    )
    latest_worksheet_safety_certificate_filename = fields.Char()
    latest_worksheet_notes_html = fields.Html(
        string="Worksheet Notes", compute="_compute_latest_worksheet", store=True,
    )

    extra_product_line_ids = fields.One2many(
        'waste.service.request.extra.line',
        'request_id',
        string='Extra Products',
    )
    extra_product_count = fields.Integer(
        compute='_compute_extra_product_count',
    )

    wizard_pickup_point_ids = fields.Many2many(
        'pickup.point',
        string='Wizard Pickup Points',
    )
    pickup_point_bins_summary = fields.Text(
        string='Pickup/Dropoff Points & Bins Summary',
        compute='_compute_pickup_point_bins_summary',
        store=True,
    )
    wizard_pickup_point_count = fields.Integer(
        compute='_compute_wizard_pickup_point_count',
    )
    bin_line_ids = fields.One2many(
        'waste.request.bin.line',
        'request_id',
        string='Pickup/Bins Lines',
    )
    bin_line_count = fields.Integer(
        compute='_compute_bin_line_count',
    )
    sale_order_count = fields.Integer(
        compute='_compute_sale_order_count',
    )

    user_line_ids = fields.One2many(
        'wmz.service.request.user',
        'service_request_id',
        string="Users"
    )


