import re
import logging
import json
import urllib.parse
from datetime import datetime, timedelta, time

from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError
from .service_provider import SA_PROVINCES

_logger = logging.getLogger(__name__)

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'

class WasteServiceRequest(models.Model):
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
        # domain=lambda self: [
        #     ('user_id.groups_id', 'in', self.env.ref('waste_management_zakheni.group_wmz_admin_clerk').ids)
        # ]

    )

    admin_clerck_email = fields.Char(
        related="employee_email_id.work_email",
        store=True
    )

    employee_manager_id = fields.Many2one(
        'hr.employee',
        string="Mailto",
        # domain=lambda self: [
        #     ('user_id.groups_id', 'in', self.env.ref('waste_management_zakheni.group_wmz_manager').ids)
        # ]

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

    disposal_site_id = fields.Many2one(
        'waste.disposal.site',
        string="Disposal Site",
        domain="[('id', 'in', allowed_disposal_site_ids)]"
    )

    # disposal_site_id = fields.Many2one(
    #     'waste.disposal.site',
    #     string="Disposal Site",
    #     domain="[('id', 'in', allowed_disposal_site_ids)]"
    # )

    disposal_site_ids = fields.Many2many(
        'waste.disposal.site',
        'waste_request_disposal_site_rel',
        'request_id',
        'disposal_site_id',
        string="Disposal Sites",
        domain="[('id', 'in', allowed_disposal_site_ids)]"
    )

    allowed_disposal_site_ids = fields.Many2many(
        'waste.disposal.site',
        compute='_compute_allowed_disposal_sites',
        string="Allowed Disposal Sites",
        store=False
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
    #
    #
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

    @api.depends('waste_type_id')
    def _compute_allowed_disposal_sites(self):

        DisposalSite = self.env['waste.disposal.site']

        for rec in self:

            if not rec.waste_type_id:
                rec.allowed_disposal_site_ids = DisposalSite.search([])
                continue

            waste_name = (rec.waste_type_id.name or '').strip().lower()

            # Hazardous
            if waste_name == 'hazardous':

                sites = DisposalSite.search([
                    '|',
                    ('waste_type', '=', 'hazardous'),
                    ('waste_type', '=', False)
                ])

            # General Compactable
            elif waste_name == 'general compactable':

                sites = DisposalSite.search([
                    '|',
                    ('waste_type', '=', 'general_compactable'),
                    ('waste_type', '=', False)
                ])

            # General Non-Compactable
            elif waste_name == 'general non-compactable':

                sites = DisposalSite.search([
                    '|',
                    ('waste_type', '=', 'general_non-compactable'),
                    ('waste_type', '=', False)
                ])

            else:
                sites = DisposalSite.search([])

            rec.allowed_disposal_site_ids = sites

    # @api.onchange('waste_type_id')
    # def _onchange_waste_type_id_disposal_site(self):
    #
    #     if not self.disposal_site_id:
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
    #     # Allow empty disposal site waste type everywhere
    #     if self.disposal_site_id.waste_type in (False, allowed_type):
    #         return
    #
    #     self.disposal_site_id = False

        @api.onchange('waste_type_id')
        def _onchange_waste_type_id_disposal_site(self):

            if not self.disposal_site_ids:
                return

            waste_name = (self.waste_type_id.name or '').strip().lower()

            allowed_type = False

            if waste_name == 'hazardous':
                allowed_type = 'hazardous'

            elif waste_name == 'general compactable':
                allowed_type = 'general_compactable'

            elif waste_name == 'general non-compactable':
                allowed_type = 'general_non-compactable'

            allowed_sites = self.disposal_site_ids.filtered(
                lambda s:
                not s.waste_type
                or s.waste_type == allowed_type
            )

            self.disposal_site_ids = allowed_sites



    @api.model
    def _get_busy_drivers_at_date(self, at_datetime):
        """
        Returns res.partner IDs of drivers that are busy
        from at_datetime onwards.
        """
        if not at_datetime:
            return []

        return self.search([
            ('planned_date', '>=', at_datetime),
            ('driver_id', '!=', False),
        ]).mapped('driver_id').ids

    @api.model
    def _get_busy_assistants_at_date(self, at_datetime):
        if not at_datetime:
            return []

        return self.search([
            ('planned_date', '>=', at_datetime),
            ('assistance_id', '!=', False),
        ]).mapped('assistance_id').ids


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




    # ---------------------------------------------------------
    # If service provider is used -> clear internal fleet assignment fields. If not -> clear provider fields.
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

    # ---------------------------------------------------------
    # Busy Drivers and assistance depend on Planned date.
    # ---------------------------------------------------------
    @api.depends('planned_date')
    def _compute_busy_drivers(self):
        now = fields.Datetime.now()
        for rec in self:
            busy = self.env['waste.service.request'].search([
                ('planned_date', '>=', now),
                ('driver_id', '!=', False),
                ('id', '!=', rec._origin.id or 0)  # ✅ safe check
            ]).mapped('driver_id').ids
            rec.busy_driver_ids = [(6, 0, busy)]

    @api.depends('planned_date')
    def _compute_busy_assistants(self):
        now = fields.Datetime.now()
        for rec in self:
            busy = self.env['waste.service.request'].search([
                ('planned_date', '>=', now),
                ('assistance_id', '!=', False),
                ('id', '!=', rec._origin.id or 0)
            ]).mapped('assistance_id').ids
            rec.busy_assistance_ids = [(6, 0, busy)]

    @api.depends('planned_date')
    def _compute_busy_trucks(self):
        now = fields.Datetime.now()
        for rec in self:
            busy = self.env['waste.service.request'].search([
                ('planned_date', '>=', now),
                ('vehicle_id', '!=', False),
                ('id', '!=', rec._origin.id or 0)
            ]).mapped('vehicle_id').ids
            rec.busy_track_ids = [(6, 0, busy)]

    @api.depends('planned_date')
    def _compute_busy_traillers(self):
        now = fields.Datetime.now()
        for rec in self:
            busy = self.env['waste.service.request'].search([
                ('planned_date', '>=', now),
                ('trailer_id', '!=', False),
                ('id', '!=', rec._origin.id or 0)
            ]).mapped('trailer_id').ids
            rec.busy_trailler_ids = [(6, 0, busy)]

    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('scheduled', 'Scheduled'),
        ('assigned', 'Assigned to Driver'),
        ('dispatched', 'Dispatched'),
        ('service_delivered', 'Service Delivered'),
        ('cancelled', 'Rejected'),
        ('done', 'Authorised'),
        ('none', 'None'),
    ], default='draft', tracking=True)

    # ✅ new helper field for human label
    state_label = fields.Char(
        string="Status Label",
        compute="_compute_state_label",
        store=False,
    )

    @api.depends('state')
    def _compute_state_label(self):
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
                    # ✅ External provider → provider required
                # if rec.is_service_provider and not rec.provider_id:
                #     raise ValidationError(
                #         _("Please Enter Service Provider by clicking on 'Find Service Provider' Button ⏩.")
                #     )

            # Required when scheduled
            if rec.state == "scheduled":

                if not rec.planned_date:
                    raise ValidationError(_("Please Enter Manifest Planned Date ⌚."))

                # ✅ Internal job → vehicle required
                if rec.planned_date and not rec.is_service_provider and not rec.vehicle_id:
                    raise ValidationError(
                        _("Please Enter Vehicle Registration Number 🚚.")
                    )

    @api.model
    def action_signature(self):
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

    # ---------------------------------------------------------
    # Check pickup point and Bins.
    # ---------------------------------------------------------
    @api.constrains('partner_id', 'pickup_point_ids', 'dropoff_point_ids', 'bin_lifted_ids')
    def _check_pickup_points_and_bins(self):
        for rec in self:
            # If no customer, nothing to validate
            if not rec.partner_id:
                continue

            # --------------------------------------------------
            # 1) Pickup points must belong to the same customer
            # --------------------------------------------------
            for pp in rec.pickup_point_ids:
                if pp.partner_id and pp.partner_id != rec.partner_id:
                    raise ValidationError(_(
                        "Pickup point '%(pp)s' belongs to customer '%(c_pp)s', "
                        "but this request is for customer '%(c_req)s'.",
                        pp=pp.display_name,
                        c_pp=pp.partner_id.display_name,
                        c_req=rec.partner_id.display_name,
                    ))

            # --------------------------------------------------
            # 2) Drop-off points must also belong to same customer
            # --------------------------------------------------
            for pp in rec.dropoff_point_ids:
                if pp.partner_id and pp.partner_id != rec.partner_id:
                    raise ValidationError(_(
                        "Drop-off point '%(pp)s' belongs to customer '%(c_pp)s', "
                        "but this request is for customer '%(c_req)s'.",
                        pp=pp.display_name,
                        c_pp=pp.partner_id.display_name,
                        c_req=rec.partner_id.display_name,
                    ))

            # --------------------------------------------------
            # 3) Bins must belong to the same customer AND
            #    be linked to one of the selected pickup points
            # --------------------------------------------------
            if not rec.pickup_point_ids or not rec.bin_lifted_ids:
                # No pickup points or no bins -> nothing more to validate
                continue

            allowed_pp_ids = set(rec.pickup_point_ids.ids)

            for cont in rec.bin_lifted_ids:
                # 3.1) Check bin's customer
                if cont.partner_id and cont.partner_id != rec.partner_id:
                    raise ValidationError(_(
                        "Bin %(bin)s belongs to customer %(c_bin)s, "
                        "but this request is for customer %(c_req)s.",
                        bin=cont.display_name,
                        c_bin=cont.partner_id.display_name,
                        c_req=rec.partner_id.display_name,
                    ))

                # 3.2) Check bin's pickup point is in selected pickup points
                if cont.pickup_point_id and cont.pickup_point_id.id not in allowed_pp_ids:
                    raise ValidationError(_(
                        "Bin %(bin)s is linked to pickup point %(pp_bin)s, "
                        "which is not in the selected pickup points for this request.",
                        bin=cont.display_name,
                        pp_bin=cont.pickup_point_id.display_name,
                    ))


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
            qty = rec.product_uom_qty or 0.0
            line.with_context(skip_waste_sync=True).write({
                'product_uom_qty': qty
            })

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
            self._sync_sale_order_qty()

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
    # Status actions
    # ---------------------------------------------------------

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_generated(self):
        for rec in self:
            # Decide which containers to mark as in use for "generated"
            targets = self.env['waste.container']
            # If your logic actually depends on service type, put that logic here.
            targets |= rec.bin_lifted_ids
            targets |= rec.bin_dropped_ids
            targets |= rec.tank_ids

            # Update in bulk. If you don't have inUse, remove it and keep status only.
            vals = {}
            if 'inUse' in targets._fields:
                vals['inUse'] = True
            if 'status' in targets._fields:
                vals['status'] = 'in_use'
            if vals:
                targets.write(vals)

            rec.state = 'generated'


    def action_set_scheduled(self):
        Worksheet = self.env['waste.worksheet'].sudo()

        for rec in self:
            # 1️⃣ Change state
            rec.state = 'scheduled'

            # 2️⃣ Create worksheet if not exists
            existing_ws = Worksheet.search([
                ('service_request_id', '=', rec.id)
            ], limit=1)

            if not existing_ws:
                Worksheet.create({
                    'service_request_id': rec.id,
                    'company_id': rec.company_id.id,
                })

            # 3️⃣ SEND EMAIL ✅
            if rec.is_service_provider:
                template = rec.env.ref(
                    "waste_management_zakheni.mail_tmpl_service_request_service_provide_invitation",
                    raise_if_not_found=False,
                )
                print("Provider Email: ", rec.provider_email)

            else:
                template = rec.env.ref(
                    "waste_management_zakheni.mail_tmpl_service_request_driver_invitation",
                    raise_if_not_found=False,
                )
                print("Driver Email: ", rec.driver_work_email)


            # 🚨 IMPORTANT CHECKS
            if template:
                if rec.is_service_provider:
                    if rec.provider_email:
                        template.sudo().send_mail(rec.id, force_send=True)
                else:
                    if rec.driver_work_email:
                        template.sudo().send_mail(rec.id, force_send=True)

        return True

    def action_mark_done(self):
        for record in self:
            # ✅ run whole logic with sudo to avoid Sales Order access errors
            rec = record.sudo()



            # Normalised service code
            svc_code = (rec.service_requested_id.code or '').lower() \
                if rec.service_requested_id and hasattr(rec.service_requested_id, 'code') \
                else (rec.service_requested_id.display_name or '').strip().lower()

            # Destination pickup points (from the request)
            dest_pps = rec.pickup_point_ids
            dest_pp_ids = dest_pps.ids
            dest_pp_label = ", ".join(dest_pps.mapped("display_name")) if dest_pps else "Unknown"

            # Customer for containers
            cust = rec.partner_id or rec.partner_id

            # -------------------------------------------------
            # REMOVAL OF BINS  -> use bin_lifted_ids
            # -------------------------------------------------
            if svc_code == 'removal of bins':
                for container in rec.bin_lifted_ids:
                    container = container.sudo()
                    if 'pickup_point_ids' in container._fields:
                        container.pickup_point_ids = [(5, 0, 0)]
                    if 'pickup_point_id' in container._fields:
                        container.pickup_point_id = False
                    if 'dropoff_point_id' in container._fields:
                        container.dropoff_point_id = False
                    if 'partner_id' in container._fields:
                        container.partner_id = False
                    if 'status' in container._fields:
                        container.status = 'intact'
                    if 'inUse' in container._fields:
                        container.inUse = False
                    # 🔹 clear reservation once the removal is completed
                    if 'reserved_request_id' in container._fields and container.reserved_request_id == rec:
                        container.reserved_request_id = False

                    rec.message_post(body=f"Removed bin: {container.display_name}")

            # -------------------------------------------------
            # SWAPPING OF BINS -> bin_lifted_ids / bin_dropped_ids
            # -------------------------------------------------
            elif svc_code == 'swapping of bins':
                # 1) Lifted bins: take them away from current points/customer
                for lifted_bin in rec.bin_lifted_ids:
                    lifted_bin = lifted_bin.sudo()
                    if 'pickup_point_ids' in lifted_bin._fields:
                        lifted_bin.pickup_point_ids = [(5, 0, 0)]
                    if 'pickup_point_id' in lifted_bin._fields:
                        lifted_bin.pickup_point_id = False
                    if 'dropoff_point_id' in lifted_bin._fields:
                        lifted_bin.dropoff_point_id = False
                    if 'partner_id' in lifted_bin._fields:
                        lifted_bin.partner_id = False
                    if 'status' in lifted_bin._fields:
                        lifted_bin.status = 'intact'
                    if 'inUse' in lifted_bin._fields:
                        lifted_bin.inUse = False
                    # 🔹 clear reservation for lifted bins as well
                    if 'reserved_request_id' in lifted_bin._fields and lifted_bin.reserved_request_id == rec:
                        lifted_bin.reserved_request_id = False

                    from_label = ", ".join(
                        lifted_bin.pickup_point_ids.mapped("display_name")
                    ) if 'pickup_point_ids' in lifted_bin._fields and lifted_bin.pickup_point_ids else "Unknown"

                    rec.message_post(
                        body=f"Lifted bin '{lifted_bin.display_name}' from '{from_label}'"
                    )

                # 2) Dropped bins: assign to destination pickup points + customer
                for dropped_bin in rec.bin_dropped_ids:
                    dropped_bin = dropped_bin.sudo()
                    dest_pp_single = dest_pps[:1] and dest_pps[0] or False

                    if 'pickup_point_ids' in dropped_bin._fields and dest_pp_ids:
                        dropped_bin.pickup_point_ids = [(6, 0, dest_pp_ids)]
                    if 'pickup_point_id' in dropped_bin._fields and dest_pp_single:
                        dropped_bin.pickup_point_id = dest_pp_single
                    if 'dropoff_point_id' in dropped_bin._fields and dest_pp_single:
                        dropped_bin.dropoff_point_id = dest_pp_single
                    if 'partner_id' in dropped_bin._fields and cust:
                        dropped_bin.partner_id = cust
                    if 'status' in dropped_bin._fields:
                        dropped_bin.status = 'in_use'
                    if 'inUse' in dropped_bin._fields:
                        dropped_bin.inUse = True
                    # 🔹 clear reservation once swap is completed
                    if 'reserved_request_id' in dropped_bin._fields and dropped_bin.reserved_request_id == rec:
                        dropped_bin.reserved_request_id = False

                    label = dest_pp_single.display_name if dest_pp_single else dest_pp_label
                    rec.message_post(
                        body=f"Dropped bin '{dropped_bin.display_name}' at '{label}'"
                    )


            elif svc_code == 'shunting of bins':

                # Safely get shunt fields
                shunt_from = rec.shunt_from_id if 'shunt_from_id' in rec._fields else False
                shunt_to = rec.shunt_to_id if 'shunt_to_id' in rec._fields else False
                shunt_bins = rec.shunt_container_ids if 'shunt_container_ids' in rec._fields else rec.env[
                    'waste.container']

                from_label = shunt_from.display_name if shunt_from else "Unknown"
                to_label = shunt_to.display_name if shunt_to else "Unknown"

                for bin_rec in shunt_bins:
                    bin_rec = bin_rec.sudo()

                    # 🔹 Set the new pickup point
                    if 'pickup_point_id' in bin_rec._fields and shunt_to:
                        bin_rec.pickup_point_id = shunt_to

                    # 🔹 Track pickup history
                    if 'pickup_point_ids' in bin_rec._fields and shunt_to:
                        bin_rec.pickup_point_ids = [(4, shunt_to.id)]

                    # 🔹 Clear received/dropoff location
                    if 'dropoff_point_id' in bin_rec._fields:
                        bin_rec.dropoff_point_id = False

                    # 🔹 Set customer
                    if 'partner_id' in bin_rec._fields and cust:
                        bin_rec.partner_id = cust

                    # 🔹 Set status
                    if 'status' in bin_rec._fields:
                        bin_rec.status = 'in_use'

                    if 'inUse' in bin_rec._fields:
                        bin_rec.inUse = True

                    # 🔹 Clear reservation
                    if 'reserved_request_id' in bin_rec._fields and bin_rec.reserved_request_id == rec:
                        bin_rec.reserved_request_id = False

                    # 🔹 Log the movement
                    rec.message_post(
                        body=f"Shunted bin '{bin_rec.display_name}' from '{from_label}' to '{to_label}'"
                    )


            elif svc_code == 'placement of bins':
                # Use each line’s pickup/dropoff to place its bins
                for line in rec.bin_line_ids:
                    # Prefer drop-off point, else pickup point
                    dest_pp = line.dropoff_point_id or line.pickup_point_id
                    label = dest_pp.display_name if dest_pp else dest_pp_label

                    for container in line.bin_dropped_ids:
                        container = container.sudo()
                        if 'pickup_point_id' in container._fields and dest_pp:
                            container.pickup_point_id = dest_pp
                        if 'pickup_point_ids' in container._fields and dest_pp:
                            container.pickup_point_ids = [(4, dest_pp.id)]
                        if 'dropoff_point_id' in container._fields and dest_pp:
                            container.dropoff_point_id = dest_pp
                        if 'partner_id' in container._fields and cust:
                            container.partner_id = cust
                        if 'status' in container._fields:
                            container.status = 'in_use'
                        if 'inUse' in container._fields:
                            container.inUse = True
                        # 🔹 important: clear reservation so bin is available
                        if 'reserved_request_id' in container._fields and container.reserved_request_id == rec:
                            container.reserved_request_id = False

                        rec.message_post(
                            body=f"Placed bin: {container.display_name} at {label}"
                        )

            elif svc_code in (
                    'waste collection & disposal',
                    'waste collection and disposal',
                    'general collection & desposal',
            ):

                for line in rec.bin_line_ids:

                    dest_pp = line.pickup_point_id
                    label = dest_pp.display_name if dest_pp else "Unknown"

                    # -------------------------------------------------
                    # 1️⃣ COLLECTED BINS (go to yard after disposal)
                    # -------------------------------------------------
                    for container in line.bin_lifted_ids:
                        container = container.sudo()

                        if 'pickup_point_ids' in container._fields:
                            container.pickup_point_ids = [(5, 0, 0)]

                        if 'pickup_point_id' in container._fields:
                            container.pickup_point_id = False

                        if 'dropoff_point_id' in container._fields:
                            container.dropoff_point_id = False

                        if 'partner_id' in container._fields:
                            container.partner_id = False

                        if 'status' in container._fields:
                            container.status = 'intact'

                        if 'inUse' in container._fields:
                            container.inUse = False

                        if 'reserved_request_id' in container._fields and container.reserved_request_id == rec:
                            container.reserved_request_id = False

                        rec.message_post(
                            body=f"Collected bin for disposal: {container.display_name}"
                        )

                    # -------------------------------------------------
                    # 2️⃣ PLACE NEW EMPTY BIN (placement logic)
                    # -------------------------------------------------
                    for container in line.bin_dropped_ids:
                        container = container.sudo()

                        if 'pickup_point_id' in container._fields and dest_pp:
                            container.pickup_point_id = dest_pp

                        if 'pickup_point_ids' in container._fields and dest_pp:
                            container.pickup_point_ids = [(4, dest_pp.id)]

                        if 'dropoff_point_id' in container._fields and dest_pp:
                            container.dropoff_point_id = dest_pp

                        if 'partner_id' in container._fields and cust:
                            container.partner_id = cust

                        if 'status' in container._fields:
                            container.status = 'in_use'

                        if 'inUse' in container._fields:
                            container.inUse = True

                        if 'reserved_request_id' in container._fields and container.reserved_request_id == rec:
                            container.reserved_request_id = False

                        rec.message_post(
                            body=f"Placed empty bin {container.display_name} at {label}"
                        )

            all_tanks = rec.env['waste.container']

            # 1) Log per-line liters + tanks
            total_liters = 0.0
            for line in rec.bin_line_ids:
                if not line.tank_ids:
                    continue

                all_tanks |= line.tank_ids

                liters = line.liters_collected or 0.0
                total_liters += liters

                pp_label = (
                    line.pickup_point_id.display_name
                    if line.pickup_point_id
                    else dest_pp_label
                )

                tank_bits = []
                for tank in line.tank_ids:
                    tank = tank.sudo()
                    # Try to show tank volume
                    vol_label = ""
                    if "tank_volume_id" in tank._fields and tank.tank_volume_id:
                        vol_label = (
                                tank.tank_volume_id.display_name
                                or tank.tank_volume_id.name
                                or ""
                        )

                    if vol_label:
                        tank_bits.append(f"{tank.display_name} ({vol_label})")
                    else:
                        tank_bits.append(tank.display_name)

                tank_label = ", ".join(tank_bits) or "Unknown tank"

                if liters:
                    msg = (
                        f"Collected {liters:g} L from tanks: {tank_label} "
                        f"at {pp_label}"
                    )
                else:
                    msg = f"Emptied tanks: {tank_label} at {pp_label}"

                rec.message_post(body=msg)

            # 1b) Log overall kL + tariff summary for the job (if this is a Tank job)
            if rec._is_tank_job():
                liters_for_billing = rec.liters_collected or total_liters
                kl = rec.billing_kl or (liters_for_billing / 1000.0 if liters_for_billing else 0.0)
                base_kl, base_price, extra_rate = rec._get_rate_params()
                extra_kl = max(0.0, kl - base_kl)
                amount = rec.billing_amount or 0.0

                tariff_msg = (
                    f"Tank job summary: {kl:.2f} kL "
                    f"({liters_for_billing:.0f} L). "
                    f"Base: {base_kl:g} kL at R{base_price:,.2f}. "
                    f"Extra: {extra_kl:.2f} kL at R{extra_rate:,.2f}/kL. "
                    f"Total amount (excl. VAT): R{amount:,.2f}."
                )
                rec.message_post(body=tariff_msg)

            # 2) Actually empty / reset tank records (keep your existing logic here)
            for tank in all_tanks:
                tank = tank.sudo()
                if "pickup_point_ids" in tank._fields:
                    tank.pickup_point_ids = [(6, 0, dest_pp_ids)]
                if "pickup_point_id" in tank._fields and dest_pps:
                    tank.pickup_point_id = dest_pps[0]
                if "dropoff_point_id" in tank._fields and dest_pps:
                    tank.dropoff_point_id = dest_pps[0]
                if "partner_id" in tank._fields and cust:
                    tank.partner_id = cust
                if "status" in tank._fields:
                    tank.status = "un_use"
                if "inUse" in tank._fields:
                    tank.inUse = False
                if (
                        "reserved_request_id" in tank._fields
                        and tank.reserved_request_id == rec
                ):
                    tank.reserved_request_id = False

            return {
                'type': 'ir.actions.act_window',
                'name': 'Authorize',
                'res_model': 'authorize.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_user_id': rec.id,
                    'default_finance_employee_id': rec.finance_employee_id.id,
                }

            }


            # ============================================================
            # ✅ SEND EMAIL TO FINANCE (NO TEMPLATE)
            # ============================================================

            # if rec.finance_email:
            #     mail_values = {
            #         'subject': f"Service Request Completed - {rec.name}",
            #         'body_html': f"""
            #             <p>Hello,</p>
            #
            #             <p>The following service request has been completed:</p>
            #
            #             <ul>
            #                 <li><strong>Request:</strong> {rec.name}</li>
            #                 <li><strong>Customer:</strong> {rec.partner_id.name or ''}</li>
            #                 <li><strong>Service:</strong> {rec.service_requested_id.display_name or ''}</li>
            #                 <li><strong>Status:</strong> {rec.state}</li>
            #             </ul>
            #
            #             <p>Please proceed with billing.</p>
            #
            #             <br/>
            #             <p>Regards,<br/>System</p>
            #         """,
            #         'email_to': rec.finance_email,
            #     }
            #
            #     rec.env['mail.mail'].sudo().create(mail_values).send()
            # tmpl = rec.env.ref(
            #     'waste_management_zakheni.mail_tmpl_service_request_authorize',
            #     raise_if_not_found=False
            # )
            #
            # if tmpl and rec.finance_email:
            #     tmpl.sudo().send_mail(
            #         rec.id,
            #         force_send=True,
            #         raise_exception=True,
            #         email_values={
            #             'email_to': rec.finance_email
            #         }
            #     )




    def action_cancelled(self):
        self.ensure_one()
        # 1) Update worksheet state (adjust target state as you prefer)
        if self.work_sheet_id and self.work_sheet_id.state in ('draft', 'in_progress', 'done'):
            # Example: move worksheet back to draft when request is cancelled
            self.work_sheet_id.with_context(skip_auto_state=True).write({
                'state': 'in_progress',
            })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Enter Reject Reason',
            'res_model': 'reject.service.request.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
            },
        }

    def action_amend(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Enter Amend Comment',
            'res_model': 'amend.service.request.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
            },
        }

    def action_open_related_sales(self):
        """Redirect to sales orders related to this customer"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Orders',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'target': 'current',
        }

    # Documents upload
    manifest_document = fields.Binary("Manifests Document", attachment=True)
    manifest_document_filename = fields.Char()

    weighbridge_slip = fields.Binary("Weighbridge Slip", attachment=True)
    weighbridge_slip_filename = fields.Char()

    safety_certificate = fields.Binary("Safety Certificate", attachment=True)
    safety_certificate_filename = fields.Char()

    def action_open_manifest_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Manifest Document',
            'res_model': 'waste.service.request',
            'view_mode': 'form',
            'view_id': self.env.ref('waste_management_zakheni.view_manifest_document_popup').id,
            'res_id': self.id,
            'target': 'new',
        }

    def action_open_weighbridge_slip(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Weighbridge Slip',
            'res_model': 'waste.service.request',
            'view_mode': 'form',
            'view_id': self.env.ref('waste_management_zakheni.view_weighbridge_slip_popup').id,
            'res_id': self.id,
            'target': 'new',
        }

    def action_open_safety_certificate(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Safety Certificate',
            'res_model': 'waste.service.request',
            'view_mode': 'form',
            'view_id': self.env.ref('waste_management_zakheni.view_safety_certificate_popup').id,
            'res_id': self.id,
            'target': 'new',
        }

    # ---------------------------------------------------------
    # Worksheet
    # ---------------------------------------------------------
    worksheet_ids = fields.One2many(
        "waste.worksheet", "service_request_id", string="Worksheet"
    )
    worksheet_count = fields.Integer(
        string="Worksheet", compute="_compute_worksheets_count"
    )

    latest_worksheet_arrival_time = fields.Datetime(string='Arrival Time', compute="_compute_latest_worksheet",
                                                    store=True)
    latest_worksheet_kilometers = fields.Integer(string='Kilometers', compute="_compute_latest_worksheet", store=True)
    latest_worksheet_return_date = fields.Datetime(string='Return Date', compute="_compute_latest_worksheet",
                                                   store=True)
    latest_worksheet_unit_of_measure = fields.Many2one('uom.uom', string='Units of Measure',
                                                       compute="_compute_latest_worksheet",
                                                       store=True)
    latest_worksheet_quantity_collected = fields.Float(string='Quantity Collected', compute="_compute_latest_worksheet",
                                                       store=True)
    latest_worksheet_driver_signature = fields.Binary(string="Signature", compute="_compute_latest_worksheet",
                                                      store=True)
    latest_worksheet_manifest_document = fields.Binary("Manifests Document", compute="_compute_latest_worksheet",
                                                       store=True, attachment=True)
    latest_worksheet_manifest_document_filename = fields.Char()

    latest_worksheet_weighbridge_slip = fields.Binary("Weighbridge Slip", compute="_compute_latest_worksheet",
                                                      store=True, attachment=True)
    latest_worksheet_weighbridge_slip_filename = fields.Char()

    latest_worksheet_safety_certificate = fields.Binary("Safety Certificate", compute="_compute_latest_worksheet",
                                                        store=True, attachment=True)
    latest_worksheet_safety_certificate_filename = fields.Char()

    latest_worksheet_notes_html = fields.Html(
        string='Worksheet Notes',
        compute="_compute_latest_worksheet",
        store=True,
        help="Notes from the latest worksheet linked to this service request.",
    )

    def _compute_worksheets_count(self):
        for rec in self:
            rec.worksheet_count = len(rec.worksheet_ids)

    @api.depends("worksheet_ids")
    def _compute_latest_worksheet(self):
        for rec in self:
            if rec.worksheet_ids:
                latest = rec.worksheet_ids[-1]  # last created schedule
                rec.latest_worksheet_arrival_time = latest.arrival_time
                rec.latest_worksheet_kilometers = latest.kilometers
                rec.latest_worksheet_return_date = latest.return_date
                rec.latest_worksheet_unit_of_measure = latest.unit_of_measure
                rec.latest_worksheet_quantity_collected = latest.quantity_collected
                rec.latest_worksheet_driver_signature = latest.driver_signature
                rec.latest_worksheet_manifest_document = latest.manifest_document
                rec.latest_worksheet_weighbridge_slip = latest.weighbridge_slip
                rec.latest_worksheet_safety_certificate = latest.safety_certificate
                rec.latest_worksheet_notes_html = latest.notes_html  # 🔹 NEW

            else:
                rec.latest_worksheet_arrival_time = False
                rec.latest_worksheet_kilometers = False
                rec.latest_worksheet_return_date = False
                rec.latest_worksheet_unit_of_measure = False
                rec.latest_worksheet_quantity_collected = False
                rec.latest_worksheet_driver_signature = False
                rec.latest_worksheet_manifest_document = False
                rec.latest_worksheet_weighbridge_slip = False
                rec.latest_worksheet_safety_certificate = False
                rec.latest_worksheet_notes_html = False  # 🔹 NEW

    def action_view_worksheet(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Worksheet",
            "res_model": "waste.worksheet",
            "view_mode": "tree,form",
            "target": "current",
            "domain": [("service_request_id", "=", self.id)],
            "context": {"default_service_request_id": self.id},
        }

    extra_product_line_ids = fields.One2many(
        'waste.service.request.extra.line',
        'request_id',
        string='Extra Products',
    )

    extra_product_count = fields.Integer(
        compute="_compute_extra_product_count",
        string="Extra Products",
    )

    @api.depends('extra_product_line_ids')
    def _compute_extra_product_count(self):
        for rec in self:
            rec.extra_product_count = len(rec.extra_product_line_ids)

    # def action_open_product_selector(self):
    #     """Smart button → fancy product grid (kanban)"""
    #     self.ensure_one()
    #     action = self.env.ref(
    #         'waste_management_zakheni.action_waste_request_product_selector'
    #     ).sudo().read()[0]
    #
    #     ctx = dict(self.env.context)
    #     ctx.update({
    #         'waste_request_id': self.id,
    #         'search_default_sale_ok': 1,  # only storable/service for sale
    #     })
    #     action['context'] = ctx
    #     return action

    def action_push_extra_products_to_so(self):
        """Create / update sale.order.line from extra products.

        - Only WMZ Admin / Admin Clerk can run it
        - sale.order.line create/write runs with sudo to avoid Sales access errors
        """
        allowed = (
                self.env.user.has_group('waste_management_zakheni.group_wmz_admin') or
                self.env.user.has_group('waste_management_zakheni.group_wmz_admin_clerk')
        )
        if not allowed:
            raise AccessDenied(_("You are not allowed to update the Sales Order."))

        SaleLine = self.env['sale.order.line'].sudo()

        for req in self:
            if not req.sale_order_id:
                raise UserError(_('No Sales Order linked to this request.'))
            so = req.sale_order_id.sudo()  # safe access

            for line in req.extra_product_line_ids:
                # Guard: product must exist
                if not line.product_id:
                    continue

                # Ensure description
                desc = (
                        line.product_id.get_product_multiline_description_sale()
                        or line.product_id.display_name
                )

                if line.sale_order_line_id:
                    # update existing SO line (sudo)
                    SaleLine.browse(line.sale_order_line_id.id).write({
                        'product_uom_qty': line.quantity,
                        'price_unit': line.price_unit,
                        'name': desc,
                    })
                else:
                    # create new SO line (sudo)
                    sol_vals = {
                        'order_id': so.id,
                        'product_id': line.product_id.id,
                        'name': desc,
                        'product_uom_qty': line.quantity,
                        'price_unit': line.price_unit,
                    }
                    sol = SaleLine.create(sol_vals)

                    # link back (normal write is fine; but keep it safe)
                    line.sudo().write({'sale_order_line_id': sol.id})

        return True

    wizard_pickup_point_ids = fields.Many2many(
        'pickup.point',
        'waste_request_wizard_pickup_rel',
        'request_id',
        'pickup_point_id',
        string="Pickup/Dropoff Points",
        help="Pickup/Dropoff points captured from Assign Bins wizard.",
    )

    # ----------------------------------------------------------------------
    # SUMMARY OF PICKUP / DROPOFF POINTS & BINS (READ-ONLY TEXT)
    # ----------------------------------------------------------------------

    pickup_point_bins_summary = fields.Text(
        string="Pickup/Dropoff Points & Bins Summary",
        compute="_compute_pickup_point_bins_summary",
        store=False,
    )

    @api.depends(
        "bin_line_ids.pickup_point_id",
        "bin_line_ids.dropoff_point_id",
        "bin_line_ids.bin_lifted_ids",
        "bin_line_ids.bin_dropped_ids",
        "bin_line_ids.tank_ids",
        "bin_line_ids.liters_collected",
        "container_type_id",
        "billing_kl",
        "liters_collected",
        "waste_type_id",
        "service_requested_id",
    )
    def _compute_pickup_point_bins_summary(self):
        user = self.env.user
        # 🔒 Portal-only user (has portal, no internal user rights)
        is_pure_portal = user.has_group("base.group_portal") and not user.has_group("base.group_user")

        for rec in self:
            # --------------------------------------------------------------
            # 1) PORTAL CUSTOMER: DO NOT TOUCH RESTRICTED MODELS
            # --------------------------------------------------------------
            if is_pure_portal:
                rec.pickup_point_bins_summary = _(
                    "Pickup, drop-off and container details are managed internally by our operations team."
                )
                # Very important: skip all logic that touches container_type_id,
                # pickup_point_ids, tank_ids, etc.
                continue

            # --------------------------------------------------------------
            # 2) INTERNAL USERS: ORIGINAL FULL LOGIC
            # --------------------------------------------------------------
            parts = []

            if rec._is_tank_job():
                # If no quantity yet, leave empty
                if not rec.billing_kl or rec.billing_kl <= 0:
                    rec.pickup_point_bins_summary = ""
                    continue

                liters = rec.liters_collected or (rec.billing_kl * 1000.0)
                base_kl, base_price, extra_rate = rec._get_rate_params()

                # extra kL above base (e.g. qty 6 → extra 2)
                extra_kl = max(0.0, rec.billing_kl - base_kl)

                service_label = (
                        rec.waste_type_id.display_name
                        or rec.service_requested_id.display_name
                        or _("Tank Service")
                )

                pp_label = ", ".join(
                    rec.pickup_point_ids.mapped("display_name")
                ) or _("No Pickup Point")

                amount = rec.billing_amount or 0.0

                # Build extra kL text
                if extra_kl > 0:
                    extra_txt = _(
                        "Base: %(base_kl).0f kL, Extra: %(extra_kl).2f kL",
                        base_kl=base_kl,
                        extra_kl=extra_kl,
                    )
                else:
                    extra_txt = _(
                        "Within base %(base_kl).0f kL",
                        base_kl=base_kl,
                    )

                summary = _(
                    "%(pp)s – %(service)s: %(kl).2f kL (%(liters).0f L). "
                    "%(extra_txt)s. "
                    "Tariff: first %(base_kl).0f kL at R%(base_price).2f, "
                    "extra kL at R%(extra_rate).2f. "
                    "Amount (excl. VAT): R%(amount).2f",
                    pp=pp_label,
                    service=service_label,
                    kl=rec.billing_kl,
                    liters=liters,
                    extra_txt=extra_txt,
                    base_kl=base_kl,
                    base_price=base_price,
                    extra_rate=extra_rate,
                    amount=amount,
                )

                rec.pickup_point_bins_summary = summary
                continue  # ✅ skip bin logic for tank jobs

            # ------------------------------------------------------------------
            # 🔹 NORMAL (BIN) LOGIC – existing behaviour
            # ------------------------------------------------------------------

            # current service code (normalized)
            svc_code = (rec.service_requested_id.code or "").lower() \
                if rec.service_requested_id and hasattr(rec.service_requested_id, "code") \
                else (rec.service_requested_id.display_name or "").strip().lower()

            for line in rec.bin_line_ids:
                pp = line.pickup_point_id
                dp = line.dropoff_point_id

                lifted_names = ", ".join(line.bin_lifted_ids.mapped("display_name")) or "-"
                dropped_names = ", ".join(line.bin_dropped_ids.mapped("display_name")) or "-"

                # --------------------------------------------------
                # Build tank + liters text for this line (if any)
                # --------------------------------------------------
                tank_infos = []
                for tank in line.tank_ids:
                    vol_label = ""
                    if hasattr(tank, "tank_volume_id") and tank.tank_volume_id:
                        vol_label = (
                                tank.tank_volume_id.display_name
                                or tank.tank_volume_id.name
                                or ""
                        )
                    if vol_label:
                        tank_infos.append(f"{tank.display_name} ({vol_label})")
                    else:
                        tank_infos.append(tank.display_name)

                tanks_label = ", ".join(tank_infos)
                line_liters = line.liters_collected or 0.0

                tank_text = ""
                if line_liters and tanks_label:
                    tank_text = f"Collected {line_liters:g} L from: {tanks_label}"
                elif line_liters:
                    tank_text = f"Collected {line_liters:g} L"
                elif tanks_label:
                    tank_text = f"Tanks: {tanks_label}"

                # --------------------------------------------------
                # Summary logic per service type
                # --------------------------------------------------

                if svc_code == "placement of bins":
                    point_label = dp.display_name if dp else (pp.display_name if pp else "Unknown")
                    text = f"{point_label} [Placed: {dropped_names}]"

                elif svc_code == "shunting of bins":
                    src = pp.display_name if pp else "Unknown"
                    dst = dp.display_name if dp else "Unknown"
                    text = f"{src} → {dst} [Shunted: {lifted_names}]"

                elif svc_code == "removal of bins":
                    point_label = pp.display_name if pp else "Unknown"
                    text = f"{point_label} [Removed: {lifted_names}]"

                elif svc_code in (
                        "waste collection & disposal",
                        "waste collection and disposal",
                        "general collection & desposal",
                ):
                    point_label = pp.display_name if pp else "Unknown"
                    if line.bin_lifted_ids and line.bin_dropped_ids:
                        text = f"{point_label} [Lifted: {lifted_names} | Dropped: {dropped_names}]"
                    elif line.bin_lifted_ids:
                        text = f"{point_label} [Lifted: {lifted_names}]"
                    elif line.bin_dropped_ids:
                        text = f"{point_label} [Dropped: {dropped_names}]"
                    else:
                        text = f"{point_label} [-]"

                elif svc_code == "swapping of bins":
                    point_label = pp.display_name if pp else "Unknown"
                    text = f"{point_label} [Lifted: {lifted_names} | Dropped: {dropped_names}]"

                else:
                    point_label = pp.display_name if pp else (dp.display_name if dp else "Unknown")
                    all_bins = (line.bin_lifted_ids | line.bin_dropped_ids).mapped("display_name")
                    if len(all_bins) > 3:
                        shown = ", ".join(all_bins[:3]) + ", " + "..."
                    else:
                        shown = ", ".join(all_bins) if all_bins else "-"
                    text = f"{point_label} [{shown}]"

                if tank_text:
                    text = f"{text} ({tank_text})"

                parts.append(text)

            rec.pickup_point_bins_summary = ", ".join(parts) if parts else ""

    wizard_pickup_point_count = fields.Integer(
        compute="_compute_wizard_pickup_point_count",
        store=False,
    )

    @api.depends("bin_line_ids.pickup_point_id")
    def _compute_wizard_pickup_point_count(self):
        for rec in self:
            # unique pickup points from persistent lines
            rec.wizard_pickup_point_count = len(set(rec.bin_line_ids.mapped("pickup_point_id").ids))

    # ----------------------------------------------------------------------
    # LINES + COUNT OF BINS FROM LINES
    # ----------------------------------------------------------------------
    bin_line_ids = fields.One2many(
        "waste.request.bin.line",
        "request_id",
        string="Pickup/Bins Lines",
    )

    bin_line_count = fields.Integer(
        compute="_compute_bin_line_count",
        store=False,
    )

    @api.depends(
        "bin_line_ids.bin_lifted_ids",
        "bin_line_ids.bin_dropped_ids",
    )
    def _compute_bin_line_count(self):
        for rec in self:
            svc_code = (rec.service_requested_id.code or "").lower() \
                if rec.service_requested_id and hasattr(rec.service_requested_id, "code") \
                else (rec.service_requested_id.display_name or "").strip().lower()

            lines = rec.bin_line_ids

            if svc_code == "placement of bins":
                # how many bins are being placed
                rec.bin_line_count = sum(len(l.bin_dropped_ids) for l in lines)

            elif svc_code == "removal of bins":
                # how many bins removed
                rec.bin_line_count = sum(len(l.bin_lifted_ids) for l in lines)

            elif svc_code == "shunting of bins":
                # how many bins shunted
                rec.bin_line_count = sum(len(l.bin_lifted_ids) for l in lines)

            elif svc_code in (
                    "waste collection & disposal",
                    "waste collection and disposal",
                    "general collection & desposal",
            ):
                # count all bins involved in collection/disposal
                rec.bin_line_count = sum(
                    len(l.bin_lifted_ids | l.bin_dropped_ids) for l in lines
                )

            elif svc_code == "swapping of bins":
                # lifted + dropped for swapping
                rec.bin_line_count = sum(
                    len(l.bin_lifted_ids) + len(l.bin_dropped_ids) for l in lines
                )

            else:
                # default: all distinct bins across all lines
                all_bins = self.env["waste.container"]
                for l in lines:
                    all_bins |= (l.bin_lifted_ids | l.bin_dropped_ids)
                rec.bin_line_count = len(all_bins)

    # ---------------------------------------------------------
    # Open wizard from smart button
    # ---------------------------------------------------------
    def action_open_bin_assignment_wizard(self):
        self.ensure_one()
        action = self.env.ref('waste_management_zakheni.action_waste_assign_bin_wizard').sudo().read()[0]
        action['context'] = {
            'default_request_id': self.id,
            'active_id': self.id,
            'active_model': self._name,
        }
        return action

    sale_order_count = fields.Integer(
        string="Sale Order Count",
        compute="_compute_sale_order_count"
    )

    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = 1 if rec.sale_order_id else 0

    def action_open_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_("No Sales Order linked to this Waste Request."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Sales Order"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_order_id.id,
            "target": "current",
        }

    # ---------------------------------------------------------
    # Print Manifest PDF
    # ---------------------------------------------------------
    # def action_print_manifest_pdf(self):
    #     self.ensure_one()
    #     if self.state != "done":
    #         raise UserError(_("Only Authorised (Done) manifests can be printed."))
    #     return self.env.ref("waste_management_zakheni.action_manifest_report_pdf").report_action(self)


    def action_print_manifest_pdf(self):
        self.ensure_one()

        if self.state not in ["done", "scheduled"]:
            raise UserError(_("Only Authorised or Scheduled manifests can be printed."))

        return self.env.ref(
            "waste_management_zakheni.action_manifest_report_pdf"
        ).report_action(self)

    def _build_dashboard_domain(self, filters=None):
        filters = filters or {}

        domain_common = []

        company, scope_domain, show_bins, show_tanks = self._company_scope_from_filters(filters)

        # ✅ apply company config restrictions everywhere
        domain_common += scope_domain

        SO = self.env["sale.order"].sudo()
        INV = self.env["account.move"].sudo()

        # ✅ allowed companies from top-right company switcher
        allowed_company_ids = self.env.companies.ids or []

        # ---------------- Safe company_id ----------------
        company_val = filters.get("company_id")
        company_id = False
        if isinstance(company_val, (list, tuple)) and company_val:
            company_id = company_val[0]
        elif isinstance(company_val, int):
            company_id = company_val
        elif isinstance(company_val, str):
            company_id = int(company_val) if company_val.isdigit() else False

        # ✅ Apply company filter:
        # - if user selected a company: force it
        # - else: use allowed companies from switcher
        if company_id:
            domain_common.append(("company_id", "=", int(company_id)))
        else:
            # IMPORTANT: so switching company in the UI actually changes dashboard
            if allowed_company_ids and "company_id" in self._fields:
                domain_common.append(("company_id", "in", allowed_company_ids))

        # ---------------- Safe partner_id (Customer) ----------------
        partner_val = filters.get("partner_id")
        partner_id = False
        if isinstance(partner_val, (list, tuple)) and partner_val:
            partner_id = partner_val[0]
        elif isinstance(partner_val, int):
            partner_id = partner_val
        elif isinstance(partner_val, str):
            partner_id = int(partner_val) if partner_val.isdigit() else False

        if partner_id:
            domain_common.append(("partner_id", "=", int(partner_id)))

        # ---------------- Manifest number ----------------
        if filters.get("manifest_number"):
            domain_common.append(("name", "ilike", filters["manifest_number"]))

        # ---------------- Ticket type ----------------
        if filters.get("ticket_type"):
            domain_common.append(("ticket_type", "=", filters["ticket_type"]))

        # ---------------- SO / Invoice filters ----------------
        so_ids = set()

        if filters.get("sale_order_number"):
            so_recs = SO.search([("name", "ilike", filters["sale_order_number"])], limit=500)
            so_ids |= set(so_recs.ids)

        if filters.get("invoice_number"):
            inv_recs = INV.search([
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("state", "!=", "cancel"),
                ("name", "ilike", filters["invoice_number"]),
            ], limit=500)

            # if you have a direct sale_order_id on invoice, use it, else fallback
            if "sale_order_id" in INV._fields:
                so_ids |= set(inv_recs.mapped("sale_order_id").ids)
            else:
                so_ids |= set(inv_recs.invoice_line_ids.mapped("sale_line_ids.order_id").ids)

        if so_ids:
            # if your manifest links to SO in another field, add alternatives here
            if "sale_order_id" in self._fields:
                domain_common.append(("sale_order_id", "in", list(so_ids)))

        # ---------------- Date filters ----------------
        domain = list(domain_common)
        if filters.get("date_from"):
            domain.append(("service_request_date", ">=", filters["date_from"]))
        if filters.get("date_to"):
            domain.append(("service_request_date", "<=", filters["date_to"]))

        return domain, domain_common

    @api.model
    def get_dashboard_kpis(self, filters=None):
        filters = filters or {}
        domain, domain_common = self._build_dashboard_domain(filters)

        today = fields.Date.context_today(self)
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())

        Request = self.env["waste.service.request"].sudo()

        open_states = ("draft", "generated", "scheduled", "assigned", "dispatched")
        open_count = Request.search_count(domain + [("state", "in", open_states)])

        # Today schedule should ALSO respect same domain_common (not date range)
        schedule_field = None
        for f in ("planned_date", "scheduled_date", "schedule_date", "dispatch_date"):
            if f in self._fields:
                schedule_field = f
                break

        scheduled_today = 0
        if schedule_field:
            scheduled_today = Request.search_count(
                domain_common
                + [
                    ("state", "=", "scheduled"),
                    (schedule_field, ">=", start_of_day),
                    (schedule_field, "<=", end_of_day),
                ]
            )

        in_progress = Request.search_count(domain + [("state", "in", ("dispatched", "service_delivered"))])
        done_count = Request.search_count(domain + [("state", "=", "done")])
        rejected_count = Request.search_count(domain + [("state", "=", "cancelled")])

        month_recs = Request.search(domain + [("state", "in", ("service_delivered", "done"))])

        tank_kl = 0.0
        billing_amount = 0.0
        for rec in month_recs:
            billing_amount += (rec.billing_amount or 0.0)
            if hasattr(rec, "_is_tank_job") and rec._is_tank_job():
                tank_kl += (rec.billing_kl or 0.0)

        return {
            "open_requests": open_count,
            "scheduled_today": scheduled_today,
            "in_progress": in_progress,
            "done_count": done_count,
            "rejected_count": rejected_count,
            "tank_kl_month": tank_kl,
            "billing_amount_month": billing_amount,
        }

    def _to_date_str(self, val):
        if not val:
            return ""
        if isinstance(val, str):
            return val[:10]
        try:
            return fields.Datetime.to_string(val)[:10]
        except Exception:
            try:
                return fields.Date.to_string(val)
            except Exception:
                return ""

    def _company_scope_from_filters(self, filters=None):
        """Return (company, scope_domain, show_bins, show_tanks)."""
        filters = filters or {}

        # resolve company
        company_id = filters.get("company_id")
        try:
            company_id = int(company_id) if company_id else False
        except Exception:
            company_id = False

        company = self.env["res.company"].sudo().browse(company_id).exists() if company_id else self.env.company.sudo()

        # safe recordsets
        Service = self.env["service.request"].sudo()
        CType = self.env["container.type"].sudo()
        WType = self.env["waste.type"].sudo()

        services = company.wmz_service_ids.sudo() if "wmz_service_ids" in company._fields else Service.browse()
        ctypes = company.wmz_container_type_ids.sudo() if "wmz_container_type_ids" in company._fields else CType.browse()
        wastes = company.wmz_waste_type_ids.sudo() if "wmz_waste_type_ids" in company._fields else WType.browse()

        scope = []

        # IMPORTANT: if company configured something, restrict; if empty config -> do NOT restrict that dimension
        if services:
            scope.append(("service_requested_id", "in", services.ids))
        if ctypes and "container_type_id" in self._fields:
            scope.append(("container_type_id", "in", ctypes.ids))
        if wastes and "waste_type_id" in self._fields:
            scope.append(("waste_type_id", "in", wastes.ids))

        # Determine dashboard mode from allowed container types (name-based fallback)
        names = " ".join((ctypes.mapped("name") or [])).lower()
        show_bins = ("bin" in names) if ctypes else True
        show_tanks = ("tank" in names) if ctypes else True

        # if they configured container types but names don't include either keyword, allow both
        if ctypes and (not show_bins and not show_tanks):
            show_bins = True
            show_tanks = True

        return company, scope, show_bins, show_tanks

    # ---------------------------------------------------------
    # SINGLE SOURCE OF TRUTH: the domain used by dashboard + navigation
    # ---------------------------------------------------------
    @api.model
    def get_dashboard_open_domain(self, filters=None):
        filters = filters or {}

        SO = self.env["sale.order"].sudo()
        INV = self.env["account.move"].sudo()
        REQ = self.env["waste.service.request"].sudo()

        # --- manifests coming from SO/Invoice filters ---
        manifest_ids_from_links = set()

        # Sales Order -> Manifest
        if filters.get("sale_order_number"):
            sos = SO.search([("name", "ilike", filters["sale_order_number"])], limit=200)
            if sos:
                manifest_ids_from_links |= set(
                    REQ.search([("sale_order_id", "in", sos.ids)]).ids
                )

        # Invoice -> Manifest
        if filters.get("invoice_number"):
            invoices = INV.search([
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("state", "!=", "cancel"),
                ("name", "ilike", filters["invoice_number"]),
            ], limit=200)

            if invoices:
                # direct invoice link (if field exists)
                if "service_request_id" in INV._fields:
                    manifest_ids_from_links |= set(invoices.mapped("service_request_id").ids)

                # indirect via sale order on invoice lines
                sos_from_inv = invoices.mapped("invoice_line_ids.sale_line_ids.order_id")
                if sos_from_inv:
                    manifest_ids_from_links |= set(
                        REQ.search([("sale_order_id", "in", sos_from_inv.ids)]).ids
                    )

        # --- base manifest domain ---
        domain = []

        if filters.get("company_id"):
            domain.append(("company_id", "=", int(filters["company_id"])))

        if filters.get("partner_id"):
            domain.append(("partner_id", "=", int(filters["partner_id"])))

        if filters.get("ticket_type"):
            domain.append(("ticket_type", "=", filters["ticket_type"]))

        # strongest: manifest_id (row click)
        if filters.get("manifest_id"):
            try:
                domain.append(("id", "=", int(filters["manifest_id"])))
            except Exception:
                pass
        elif filters.get("manifest_number"):
            domain.append(("name", "ilike", filters["manifest_number"]))

        # SO/Invoice should filter manifests ONLY when no explicit manifest filter
        if manifest_ids_from_links and not (filters.get("manifest_id") or filters.get("manifest_number")):
            domain.append(("id", "in", list(manifest_ids_from_links)))

        # Date filters for manifests
        if filters.get("date_from"):
            domain.append(("service_request_date", ">=", filters["date_from"]))
        if filters.get("date_to"):
            domain.append(("service_request_date", "<=", filters["date_to"]))

        return domain

    # ---------------------------------------------------------
    # Dashboard payload (ALL tables/charts must use same domain)
    # ---------------------------------------------------------
    @api.model
    def get_dashboard_payload(self, filters=None):
        filters = filters or {}

        company, scope_domain, show_bins, show_tanks = self._company_scope_from_filters(filters)

        # ✅ Multi-company context (top-right company switcher)
        allowed_company_ids = self.env.companies.ids  # comes from allowed_company_ids in context

        domain, domain_common = self._build_dashboard_domain(filters)
        recs = self.with_context(allowed_company_ids=self.env.context.get("allowed_company_ids")).sudo().search(domain)

        SO = self.env["sale.order"].sudo()
        INV = self.env["account.move"].sudo()
        REQ = self.env["waste.service.request"].sudo()
        Partner = self.env["res.partner"].sudo()
        Users = self.env["res.users"].sudo()

        # ---------------- Helper ----------------
        def _date_to_str(val, fmt="%Y-%m-%d"):
            if not val:
                return ""
            if isinstance(val, str):
                return val[:10] if fmt == "%Y-%m-%d" else val[:7]
            return val.strftime(fmt)

        # ---------------- Customers dropdown ----------------
        customers_rs = Partner.search([
            ("is_company", "=", True),
            ("customer_rank", ">", 0),
        ], limit=1000)
        customers = [{"id": p.id, "name": p.display_name} for p in customers_rs]

        # ---------------- MAIN DOMAIN (single truth) ----------------
        domain = self.get_dashboard_open_domain(filters)
        recs = self.sudo().search(domain)

        # ---------------- Tank kL by Customer (Y=Customer, X=kL) ----------------
        tank_by_customer = []
        if "partner_id" in self._fields and "billing_kl" in self._fields:
            totals = {}
            for m in recs:
                partner = m.partner_id.display_name if m.partner_id else "Unknown"
                totals[partner] = totals.get(partner, 0.0) + float(m.billing_kl or 0.0)

            tank_by_customer = [{"customer": k, "kl": float(v)} for k, v in totals.items()]
            tank_by_customer.sort(key=lambda x: x["kl"], reverse=True)
            tank_by_customer = tank_by_customer[:12]  # top 12

        # ---------------- KPIs ----------------
        kpis = {
            "open_requests": self.search_count(domain + [
                ("state", "in", ["draft", "generated", "scheduled", "assigned", "dispatched", "service_delivered"])
            ]),
            "scheduled_count": self.search_count(domain + [("state", "=", "scheduled")]),
            "in_progress": self.search_count(
                domain + [("state", "in", ["assigned", "dispatched", "service_delivered"])]),
            "done_count": self.search_count(domain + [("state", "=", "done")]),
            "rejected_count": self.search_count(domain + [("state", "=", "cancelled")]),
            "tank_kl_month": 0.0,
            "billing_amount_month": 0.0,
        }

        if not show_tanks:
            kpis["tank_kl_month"] = 0.0

        if "billing_kl" in self._fields:
            kpis["tank_kl_month"] = float(sum(recs.mapped("billing_kl") or []) or 0.0)
        if "billing_amount" in self._fields:
            kpis["billing_amount_month"] = float(sum(recs.mapped("billing_amount") or []) or 0.0)

        # ---------------- Charts ----------------
        by_status = self.read_group(domain, ["__count"], ["state"], lazy=False)
        by_service = self.read_group(domain, ["__count"], ["service_requested_id"], lazy=False)

        top_customers = self.read_group(domain, ["__count"], ["partner_id"], lazy=False)
        top_customers = sorted(top_customers, key=lambda x: x.get("__count", 0), reverse=True)[:10]

        # ---------------- Manifest Table (Summary) ----------------
        manifest_summary = []
        mf_fields = ["id", "name", "partner_id", "state", "billing_amount", "service_requested_id",
                     "service_request_date"]
        if "bin_lifted_ids" in self._fields:
            mf_fields.append("bin_lifted_ids")
        if "bin_dropped_ids" in self._fields:
            mf_fields.append("bin_dropped_ids")

        mf_rows = self.search_read(domain, mf_fields, limit=50, order="service_request_date desc")

        for r in mf_rows[:10]:
            lifted = len(r.get("bin_lifted_ids") or [])
            dropped = len(r.get("bin_dropped_ids") or [])
            manifest_summary.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "partner_id": r.get("partner_id"),
                "partner": r["partner_id"][1] if r.get("partner_id") else "",
                "state": r.get("state"),
                "service": r["service_requested_id"][1] if r.get("service_requested_id") else "",
                "service_request_date": r.get("service_request_date") or "",
                "date": _date_to_str(r.get("service_request_date"), "%Y-%m-%d"),
                "amount": float(r.get("billing_amount") or 0.0),
                "bin_lifted": lifted,
                "bin_dropped": dropped,
                "bin_count": lifted + dropped,
            })

        manifests = [{
            "id": r.get("id"),
            "name": r.get("name"),
            "customer": r["partner_id"][1] if r.get("partner_id") else "",
            "state": r.get("state"),
            "bin_count": len(r.get("bin_lifted_ids") or []) + len(r.get("bin_dropped_ids") or []),
        } for r in mf_rows]

        # ---------------- Customer by Service ----------------
        customer_by_service = []
        groups = self.read_group(domain, ["__count"], ["partner_id", "service_requested_id"], lazy=False)
        for g in groups:
            customer_by_service.append({
                "customer": g["partner_id"][1] if g.get("partner_id") else "Unknown",
                "service": g["service_requested_id"][1] if g.get("service_requested_id") else "Unknown",
                "count": g.get("__count", 0),
            })
        customer_by_service = sorted(customer_by_service, key=lambda x: x["count"], reverse=True)

        # ---------------- Driver by trips ----------------
        driver_by_trips = []
        driver_counts = {}
        if "driver_id" in self._fields:
            rows_driver = self.search_read(domain, ["driver_id"])
            for r in rows_driver:
                d = r.get("driver_id")
                if not d:
                    continue
                driver_counts[d[1]] = driver_counts.get(d[1], 0) + 1
        for name, cnt in sorted(driver_counts.items(), key=lambda x: x[1], reverse=True):
            driver_by_trips.append({"driver": name, "trips": cnt})

        # ---------------- Revenue analysis (by month) ----------------
        revenue = {}
        if "service_request_date" in self._fields and "billing_amount" in self._fields:
            rev_rows = self.search_read(domain, ["service_request_date", "billing_amount"])
            for r in rev_rows:
                dt = r.get("service_request_date")
                if not dt:
                    continue
                key = _date_to_str(dt, "%Y-%m")
                revenue[key] = revenue.get(key, 0.0) + float(r.get("billing_amount") or 0.0)
        revenue_analysis = [{"label": k, "amount": float(v)} for k, v in sorted(revenue.items())]

        revenue_by_customer = []
        if "partner_id" in self._fields and "billing_amount" in self._fields:
            totals = {}
            for m in recs:
                partner = m.partner_id.display_name if m.partner_id else "Unknown"
                totals[partner] = totals.get(partner, 0.0) + float(m.billing_amount or 0.0)

            revenue_by_customer = [{"customer": k, "amount": float(v)} for k, v in totals.items()]
            revenue_by_customer.sort(key=lambda x: x["amount"], reverse=True)
            revenue_by_customer = revenue_by_customer[:12]  # top 12

        # ✅ Multi-company context (top-right company switcher)
        allowed_company_ids = self.env.context.get("allowed_company_ids") or self.env.companies.ids or []

        # ✅ Revenue by Company (SAFE even if billing_amount is computed/non-stored)
        revenue_by_company = []
        if "company_id" in self._fields and "billing_amount" in self._fields:
            totals = {}  # key: company_id (or 0) -> {"company": name, "amount": float}

            for m in recs:
                c = m.company_id
                cid = c.id if c else 0
                cname = c.display_name if c else "No Company"

                if cid not in totals:
                    totals[cid] = {"company": cname, "amount": 0.0}

                # IMPORTANT: read_group often returns 0 when field is computed.
                # This uses record values directly.
                totals[cid]["amount"] += float(m.billing_amount or 0.0)

            revenue_by_company = sorted(totals.values(), key=lambda x: x["amount"], reverse=True)

        _logger.info("Revenue by company result: %s", revenue_by_company)

        # ✅ Companies dropdown (only allowed companies from switcher)
        companies_rs = self.env["res.company"].sudo().browse(self.env.companies.ids).exists()
        companies = [{"id": c.id, "name": c.name} for c in companies_rs]

        gran = filters.get("tank_granularity") or "day"
        now = fields.Datetime.now()

        if filters.get("date_from"):
            df = filters["date_from"]
            start = fields.Datetime.from_string((df + " 00:00:00") if isinstance(df, str) else df)
        else:
            start = now - timedelta(days=180 if gran == "week" else 60)

        tank_domain = list(domain) + [
            ("service_request_date", ">=", fields.Datetime.to_string(start)),
            ("service_request_date", "<=", fields.Datetime.to_string(now)),
        ]

        tank_domain_with_type = list(tank_domain)
        if "container_type_id" in self._fields:
            tank_domain_with_type += [("container_type_id.name", "ilike", "tank")]

        use_domain = tank_domain_with_type if self.search_count(tank_domain_with_type) else tank_domain

        tank_series = []
        if "billing_kl" in self._fields:
            tank_rows = self.search_read(use_domain, ["service_request_date", "billing_kl"])
            bucket = {}
            for r in tank_rows:
                dt = r.get("service_request_date")
                if not dt:
                    continue
                dt_obj = fields.Datetime.from_string(dt) if isinstance(dt, str) else dt
                if gran == "week":
                    iso = dt_obj.isocalendar()
                    key = f"{iso.year}-W{iso.week:02d}"
                else:
                    key = dt_obj.strftime("%Y-%m-%d")
                bucket[key] = bucket.get(key, 0.0) + float(r.get("billing_kl") or 0.0)

            tank_series = [{"label": k, "kl": float(v)} for k, v in sorted(bucket.items(), key=lambda x: x[0])]

        # ---------------- Today schedule + assignment pie ----------------
        schedule_states = ["scheduled", "assigned", "dispatched"]
        schedule_field = None
        for f in ("planned_date", "scheduled_date", "schedule_date", "dispatch_date"):
            if f in self._fields:
                schedule_field = f
                break

        todays = []
        assignment_pie = {"labels": ["Driver Jobs", "Service Provider Jobs"], "values": [0, 0]}

        if schedule_field:
            today_local = fields.Date.context_today(self)
            broad_domain = list(domain) + [
                ("state", "in", schedule_states),
                (schedule_field, "!=", False),
            ]
            today_fields = ["id", "name", "partner_id", schedule_field, "vehicle_id", "driver_id", "state",
                            "is_service_provider", "provider_id"]
            today_fields = [f for f in today_fields if f in self._fields]

            candidates = self.search_read(broad_domain, today_fields, order=f"{schedule_field} asc", limit=500)

            filtered = []
            for r in candidates:
                dt = r.get(schedule_field)
                if not dt:
                    continue
                dt_utc = fields.Datetime.from_string(dt) if isinstance(dt, str) else dt
                dt_local = fields.Datetime.context_timestamp(self, dt_utc)
                if dt_local.date() == today_local:
                    filtered.append(r)

            todays = filtered

            sp_count = 0
            driver_count = 0
            for r in todays:
                if r.get("is_service_provider") or r.get("provider_id"):
                    sp_count += 1
                else:
                    driver_count += 1

            assignment_pie = {
                "labels": ["Driver Jobs", "Service Provider Jobs"],
                "values": [driver_count, sp_count],
            }

        # ---------------- Users pie ----------------
        user_domain = []
        if filters.get("company_id"):
            user_domain.append(("company_id", "=", int(filters["company_id"])))

        if filters.get("partner_id"):
            pid = int(filters["partner_id"])
            pids = Partner.search([("id", "child_of", pid)]).ids
            user_domain.append(("partner_id", "in", pids or [pid]))

        active_users = Users.search(user_domain + [("active", "=", True)])
        inactive_count = Users.search_count(user_domain + [("active", "=", False)])

        internal_active = active_users.filtered(lambda u: u.has_group("base.group_user"))
        portal_active = active_users.filtered(
            lambda u: u.has_group("base.group_portal") and not u.has_group("base.group_user"))

        users_pie = {
            "labels": ["Internal (Active)", "Portal (Active)", "Inactive"],
            "values": [len(internal_active), len(portal_active), int(inactive_count)],
        }

        # ---------------- Bin Report (Dropped) TABLE ----------------
        bin_report_table = []
        bin_dropped_field = "bin_dropped_ids"

        if bin_dropped_field in self._fields:
            drop_rows = self.search_read(
                domain,
                [f for f in [
                    "id", "name", "pickup_point_id", "pickup_point_ids", "dropoff_point_ids",
                    "bin_line_ids", bin_dropped_field, "service_request_date",
                ] if f in self._fields],
                limit=80,
                order="service_request_date desc"
            )

            def _get_point_label_from_row(row):
                if row.get("pickup_point_id"):
                    return row["pickup_point_id"][1]

                line_ids = row.get("bin_line_ids") or []
                if line_ids:
                    Line = self.env["waste.request.bin.line"].sudo()
                    line = Line.browse(line_ids[0]).exists()
                    if line:
                        if getattr(line, "dropoff_point_id", False):
                            return line.dropoff_point_id.display_name
                        if getattr(line, "pickup_point_id", False):
                            return line.pickup_point_id.display_name

                pp_ids = row.get("pickup_point_ids") or []
                dp_ids = row.get("dropoff_point_ids") or []
                all_ids = dp_ids or pp_ids
                if all_ids:
                    pts = self.env["pickup.point"].sudo().browse(all_ids).exists()
                    return ", ".join(pts.mapped("display_name"))
                return ""

            all_container_ids = set()
            for r in drop_rows:
                for cid in (r.get(bin_dropped_field) or []):
                    all_container_ids.add(cid)

            container_name_map = {}
            if all_container_ids:
                Container = self.env["waste.container"].sudo() if "waste.container" in self.env else self.env[
                    "stock.lot"].sudo()
                for c in Container.browse(list(all_container_ids)).exists():
                    container_name_map[c.id] = c.display_name

            for r in drop_rows:
                manifest_name = r.get("name") or ""
                drop_point = _get_point_label_from_row(r)
                date_str = _date_to_str(r.get("service_request_date"), "%Y-%m-%d")

                for cid in (r.get(bin_dropped_field) or []):
                    bin_report_table.append({
                        "key": f"{manifest_name}:{cid}",
                        "manifest": manifest_name,
                        "dropoff_point": drop_point,
                        "bin": container_name_map.get(cid, str(cid)),
                        "date": date_str,
                        "request_id": [r.get("id"), manifest_name] if r.get("id") else False,
                    })

            bin_report_table = bin_report_table[:10]

        # ---------------- Bin Report (CHART) ----------------
        lifted_total = 0
        dropped_total = 0

        if "bin_lifted_ids" in self._fields:
            for r in self.search_read(domain, ["bin_lifted_ids"]):
                lifted_total += len(r.get("bin_lifted_ids") or [])
        if "bin_dropped_ids" in self._fields:
            for r in self.search_read(domain, ["bin_dropped_ids"]):
                dropped_total += len(r.get("bin_dropped_ids") or [])

        bin_report = [
            {"label": "Bins Lifted", "count": int(lifted_total)},
            {"label": "Bins Dropped", "count": int(dropped_total)},
        ]
        # bin_report_chart = [{"label": "Total Bins Lifted", "count": int(lifted_total)}]

        bin_report_chart = [
            {"label": "Bins Lifted", "count": int(lifted_total)},
            {"label": "Bins Dropped", "count": int(dropped_total)},
        ]

        # ---------------- Bin Revenue (TABLE + CHART) ----------------
        bin_revenue_table = []
        bin_revenue_chart = []

        has_bins = ("bin_lifted_ids" in self._fields) or ("bin_dropped_ids" in self._fields)
        if has_bins and ("sale_order_id" in self._fields):
            rev_fields = ["sale_order_id", "order_line_id", "service_request_date"]
            if "bin_lifted_ids" in self._fields:
                rev_fields.append("bin_lifted_ids")
            if "bin_dropped_ids" in self._fields:
                rev_fields.append("bin_dropped_ids")

            rev_rows = self.sudo().search_read(domain, rev_fields, limit=2000)

            all_container_ids = set()
            for r in rev_rows:
                for cid in (r.get("bin_lifted_ids") or []):
                    all_container_ids.add(cid)
                for cid in (r.get("bin_dropped_ids") or []):
                    all_container_ids.add(cid)

            container_name_map = {}
            if all_container_ids:
                Container = self.env["waste.container"].sudo() if "waste.container" in self.env else self.env[
                    "stock.lot"].sudo()
                for c in Container.browse(list(all_container_ids)).exists():
                    container_name_map[c.id] = c.display_name

            per_bin = {}
            SOL = self.env["sale.order.line"].sudo()

            for r in rev_rows:
                lifted_ids = r.get("bin_lifted_ids") or []
                dropped_ids = r.get("bin_dropped_ids") or []
                bin_ids = list(set(lifted_ids + dropped_ids))
                if not bin_ids:
                    continue

                so_id = r.get("sale_order_id") and r["sale_order_id"][0]
                if not so_id:
                    continue

                line = False
                if r.get("order_line_id"):
                    line = SOL.browse(r["order_line_id"][0]).exists()

                if not line:
                    so = SO.browse(so_id).exists()
                    line = so.order_line[:1] if so else False

                if not line:
                    continue

                qty = float(line.product_uom_qty or 0.0)
                if qty <= 0:
                    continue

                subtotal = float(line.price_subtotal or 0.0)
                per_bin_amount = subtotal / qty if subtotal else 0.0

                for bid in bin_ids:
                    rec = per_bin.setdefault(bid, {
                        "revenue": 0.0, "trips": 0, "lifted": 0, "dropped": 0,
                        "qty": 0.0, "price_unit": 0.0, "line_total": 0.0
                    })
                    rec["revenue"] += per_bin_amount
                    rec["trips"] += 1
                    if bid in lifted_ids:
                        rec["lifted"] += 1
                    if bid in dropped_ids:
                        rec["dropped"] += 1

                    rec["qty"] = qty
                    rec["price_unit"] = float(line.price_unit or 0.0)
                    rec["line_total"] = subtotal

            top = sorted(per_bin.items(), key=lambda x: x[1]["revenue"], reverse=True)[:10]
            for bid, vals in top:
                bin_revenue_table.append({
                    "key": f"binrev:{bid}",
                    "bin_id": bid,
                    "bin": container_name_map.get(bid, str(bid)),
                    "revenue": float(vals["revenue"]),
                    "trips": int(vals["trips"]),
                    "lifted": int(vals["lifted"]),
                    "dropped": int(vals["dropped"]),
                    "so_qty": float(vals["qty"]),
                    "so_price_unit": float(vals["price_unit"]),
                    "so_line_total": float(vals["line_total"]),
                })

            # ✅ IMPORTANT: include bin_id so chart click can open correct domain
            bin_revenue_chart = [{
                "bin_id": row["bin_id"],
                "label": row["bin"],
                "amount": row["revenue"],
            } for row in bin_revenue_table]

        # ---------------------------------------------------------
        # Sales Order ↔ Invoice (Totals) — MUST follow current manifest domain
        # ---------------------------------------------------------
        # Manifests currently shown by current dashboard domain (may be 1 or many)
        manifest_ids_current = recs.ids

        # SOs linked to those manifests (via manifest.sale_order_id)
        so_ids_linked = set()
        if "sale_order_id" in self._fields and manifest_ids_current:
            so_ids_linked = set(recs.mapped("sale_order_id").ids)

        # Base invoice domain
        inv_domain = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "!=", "cancel"),
        ]

        # Invoice number filter (if user typed it)
        if filters.get("invoice_number"):
            inv_domain.append(("name", "ilike", filters["invoice_number"]))

        # Customer tree filter for invoices
        partner_ids = []
        if filters.get("partner_id"):
            pid = int(filters["partner_id"])
            partner_ids = Partner.search([("id", "child_of", pid)]).ids
        if partner_ids:
            inv_domain.append(("partner_id", "in", partner_ids))

        # ✅ IMPORTANT: Keep invoices inside current manifest scope:
        # (direct invoice → manifest) OR (invoice lines → SO linked to manifest)
        scope_parts = []

        # Direct link: account.move.service_request_id -> waste.service.request
        if manifest_ids_current and ("service_request_id" in INV._fields):
            scope_parts.append(("service_request_id", "in", manifest_ids_current))

        # Indirect link: invoice_line -> sale_line -> sale_order (linked to manifests)
        if so_ids_linked:
            scope_parts.append(("invoice_line_ids.sale_line_ids.order_id", "in", list(so_ids_linked)))

        # Apply scope
        if scope_parts:
            if len(scope_parts) == 1:
                inv_domain.append(scope_parts[0])
            else:
                # prepend OR operators: for N conditions you need N-1 "|"
                inv_domain += ["|"] * (len(scope_parts) - 1) + scope_parts

            invoices = INV.search(inv_domain, limit=200)
        else:
            invoices = INV.browse([])

        # Build table rows
        so_invoice_map = []
        for inv in invoices:
            so_recs = inv.invoice_line_ids.mapped("sale_line_ids.order_id")

            # If invoice has SOs, create rows per SO
            if so_recs:
                for so in so_recs:
                    # If we have a manifest SO scope, keep only those SOs
                    if so_ids_linked and so.id not in so_ids_linked:
                        continue
                    so_invoice_map.append({
                        "key": f"{so.name}|{inv.name}",
                        "sale_order": so.name,
                        "invoice": inv.name,
                        "total": float(inv.amount_total or 0.0),
                        "invoice_id": [inv.id, inv.name],
                    })
            else:
                # Invoice linked directly to manifest (service_request_id) but no SO lines
                so_invoice_map.append({
                    "key": f"NOSO|{inv.name}",
                    "sale_order": "",
                    "invoice": inv.name,
                    "total": float(inv.amount_total or 0.0),
                    "invoice_id": [inv.id, inv.name],
                })

        # Limit visible rows
        so_invoice_totals = [{
            "key": x["key"],
            "sale_order": x["sale_order"],
            "invoice": x["invoice"],
            "total": x["total"],
            "invoice_id": x["invoice_id"],
        } for x in so_invoice_map[:10]]

        # ---------------- Sales Orders by Customer (must work even if no linked SOs) ----------------
        so_by_customer = []

        so_domain = []
        # optional: limit to SOs linked to current manifests if available
        if so_ids_linked:
            so_domain.append(("id", "in", list(so_ids_linked)))

        # apply date filters to SO
        if filters.get("date_from"):
            so_domain.append(("date_order", ">=", filters["date_from"]))
        if filters.get("date_to"):
            so_domain.append(("date_order", "<=", filters["date_to"]))

        # apply SO number filter
        if filters.get("sale_order_number"):
            so_domain.append(("name", "ilike", filters["sale_order_number"]))

        # partner tree filter
        so_partner_ids = []
        if filters.get("partner_id"):
            pid = int(filters["partner_id"])
            so_partner_ids = Partner.search([("id", "child_of", pid)]).ids
            so_domain.append(("partner_id", "in", so_partner_ids or [pid]))

        # if there is no domain at all, avoid read_group on []
        if so_domain:
            so_groups = SO.read_group(so_domain, ["__count"], ["partner_id"], lazy=False)
        else:
            so_groups = []

        for g in so_groups:
            so_by_customer.append({
                "customer": g["partner_id"][1] if g.get("partner_id") else "Unknown",
                "count": g.get("__count", 0),
            })

        so_by_customer = sorted(so_by_customer, key=lambda x: x["count"], reverse=True)

        so_by_manifest = []

        if not show_bins:
            bin_report_table = []
            bin_report = []
            bin_report_chart = []
            bin_revenue_table = []
            bin_revenue_chart = []

        if not show_tanks:
            tank_series = []
            tank_by_customer = []

        return {
            "customers": customers,
            "companies": companies,  # ✅ NEW
            "kpis": kpis,
            "by_status": by_status,
            "by_service": by_service,
            "top_customers": top_customers,
            "tank_series": tank_series,
            "todays": todays,
            "assignment_pie": assignment_pie,
            "users_pie": users_pie,

            "manifest_summary": manifest_summary,
            "manifests": manifests,

            "so_invoice_totals": so_invoice_totals,
            "so_invoice_map": so_invoice_map,

            "bin_report_table": bin_report_table,
            "bin_report": bin_report,
            "bin_report_chart": bin_report_chart,

            "bin_revenue_table": bin_revenue_table,
            "bin_revenue_chart": bin_revenue_chart,

            "customer_by_service": customer_by_service,
            "driver_by_trips": driver_by_trips,
            "revenue_analysis": revenue_analysis,
            "revenue_by_customer": revenue_by_customer,
            "tank_by_customer": tank_by_customer,
            "revenue_by_company": revenue_by_company,

            "so_by_customer": so_by_customer,
            "so_by_manifest": so_by_manifest,

            "mode": {
                "show_bins": bool(show_bins),
                "show_tanks": bool(show_tanks),
                "company_id": company.id,
                "company_name": company.name,
            },

        }

    @api.model
    def get_dashboard_open_domain(self, filters=None):
        domain, _domain_common = self._build_dashboard_domain(filters or {})
        return domain

    @api.model
    def action_print_dashboard_report(self, filters=None):
        filters = filters or {}
        domain, _domain_common = self._build_dashboard_domain(filters)
        docs = self.search(domain, order="service_request_date desc")
        data = {"filters": filters, "printed_at": fields.Datetime.now()}
        return self.env.ref("waste_management_zakheni.action_waste_dashboard_report_pdf").report_action(docs, data=data)

    @api.model
    def action_export_dashboard_xlsx(self, filters=None):
        """
        Called from JS: returns an URL action to download the XLSX.
        Filters are passed through to the controller.
        """
        filters = filters or {}
        filters_json = urllib.parse.quote(json.dumps(filters))
        return {
            "type": "ir.actions.act_url",
            "url": f"/waste_dashboard/export_xlsx?filters={filters_json}",
            "target": "self",
        }

    user_line_ids = fields.One2many(
        'wmz.service.request.user',
        'service_request_id',
        string="Users"
    )

    def action_open_create_user_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create User',
            'res_model': 'wmz.create.user.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_service_request_id': self.id,
                'default_email': self.partner_id.email,
                'default_name': self.partner_id.name,
            }
        }





