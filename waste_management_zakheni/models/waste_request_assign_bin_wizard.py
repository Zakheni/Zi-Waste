from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied, ValidationError

class WasteAssignBinWizard(models.TransientModel):
    _name = 'waste.request.assign.bin.wizard'
    _description = 'Assign Bins to Pickup Points Wizard'

    request_id = fields.Many2one(
        'waste.service.request',
        string="Service Request",
        required=True,
        readonly=True,
    )

    # Service metadata
    svc_code = fields.Char(compute="_compute_svc_metadata", store=False)
    partner_id = fields.Many2one('res.partner', compute="_compute_svc_metadata", store=False)
    bin_type_id = fields.Many2one('bin.type', compute="_compute_svc_metadata", store=False)

    # Waste type (for visibility rules / future use)
    waste_type_id = fields.Many2one(
        'waste.type',
        related='request_id.waste_type_id',
        store=False,
        readonly=True,
    )
    waste_type_name = fields.Char(
        related='request_id.waste_type_id.name',
        store=False,
        readonly=True,
    )

    # Drives visibility for Bin Dropped column
    show_bin_dropped = fields.Boolean(
        string="Show Bin Dropped",
        compute="_compute_visibility_flags",
        store=False,
    )

    line_ids = fields.One2many(
        'waste.request.assign.bin.line.wizard',
        'wizard_id',
        string="Lines",
    )

    # ------------------------------------------------------------
    # Service metadata
    # ------------------------------------------------------------
    @api.depends('request_id')
    def _compute_svc_metadata(self):
        for wiz in self:
            req = wiz.request_id
            if not req:
                wiz.svc_code = ''
                wiz.partner_id = False
                wiz.bin_type_id = False
                continue

            code = (req.service_requested_id.code or '').lower() \
                if req.service_requested_id and hasattr(req.service_requested_id, 'code') \
                else (req.service_requested_id.display_name or '').strip().lower()

            wiz.svc_code = code
            wiz.partner_id = req.partner_id or req.partner_id
            wiz.bin_type_id = req.bin_type_id

    # ------------------------------------------------------------
    # Visibility flags (NO tank logic anymore)
    # ------------------------------------------------------------
    @api.depends('svc_code', 'waste_type_name', 'bin_type_id')
    def _compute_visibility_flags(self):
        for wiz in self:
            code = (wiz.svc_code or '').strip().lower()
            wt_name = (wiz.waste_type_name or '').strip().lower()

            # Bin Dropped visible for:
            # - placement of bins
            # - swapping of bins
            # - waste collection & disposal (including typo variant)
            # - special case: general collection & desposal + General Compactable
            show_bin_dropped = False
            if code in (
                'placement of bins',
                'swapping of bins',
                'waste collection & disposal',
                'waste collection and disposal',
            ):
                show_bin_dropped = True

            if code in ('waste collection & disposal', 'waste collection and disposal') \
               and wt_name == 'general compactable':
                show_bin_dropped = True

            wiz.show_bin_dropped = show_bin_dropped

    # ------------------------------------------------------------
    # LOAD STORED LINES WHEN OPENING
    # ------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if not active_id:
            return res

        req = self.env['waste.service.request'].browse(active_id)
        res['request_id'] = req.id

        lines = []
        for l in req.bin_line_ids:
            lines.append((0, 0, {
                'request_id': req.id,
                'pickup_point_id': l.pickup_point_id.id,
                'dropoff_point_id': l.dropoff_point_id.id if l.dropoff_point_id else False,
                'bin_lifted_ids': [(6, 0, l.bin_lifted_ids.ids)],
                'bin_dropped_ids': [(6, 0, l.bin_dropped_ids.ids)],
                'tank_ids': [(6, 0, l.tank_ids.ids)],
                'liters_collected': l.liters_collected,
                'liters_remaining': l.liters_remaining,
            }))

        if lines:
            res['line_ids'] = lines

        return res

    # ------------------------------------------------------------
    # APPLY = SAVE LINES PERMANENTLY + SYNC REQUEST FIELDS
    # ------------------------------------------------------------

    def action_confirm(self):
        self.ensure_one()
        req = self.request_id
        svc = (self.svc_code or '').strip().lower()
        cust = self.partner_id or req.partner_id or req.partner_id

        # clear old persistent bin lines
        req.bin_line_ids.unlink()

        persistent_vals = []
        all_lifted = self.env['waste.container']
        all_dropped = self.env['waste.container']
        all_tanks = self.env['waste.container']
        total_liters_collected = 0.0  # 🔹 new

        # collect pickup & dropoff points from wizard lines
        pickup_points = self.env['pickup.point']
        dropoff_points = self.env['pickup.point']

        # ---- NEW: prevent same bin on multiple lines ----------------
        # container_id -> (pickup_name, dropoff_name)
        bin_usage_map = {}

        for line in self.line_ids:
            # -----------------------------
            # ensure pickup_point_id is set
            # -----------------------------
            pp_id = line.pickup_point_id.id if line.pickup_point_id else False
            dp_id = line.dropoff_point_id.id if line.dropoff_point_id else False

            # For PLACEMENT OF BINS:
            # UI only asks for Drop-off Point, so technically required
            # pickup_point_id will be mirrored from dropoff_point_id
            if svc == 'placement of bins' and not pp_id:
                pp_id = dp_id

            # safety: if after that we still don't have pp_id, raise clear error
            if not pp_id:
                raise ValidationError(_("Pickup Point is required on bin mapping line."))

            # ---- DUPLICATE BIN VALIDATION --------------------------
            pp_name = line.pickup_point_id.display_name or _("(no pickup)")
            dp_name = line.dropoff_point_id.display_name or _("(no drop-off)")

            # all bins on this line (lifted + dropped)
            current_bin_ids = set(line.bin_lifted_ids.ids + line.bin_dropped_ids.ids)

            for cid in current_bin_ids:
                if cid in bin_usage_map:
                    prev_pp_name, prev_dp_name = bin_usage_map[cid]
                    bin_rec = self.env['waste.container'].browse(cid)
                    raise ValidationError(_(
                        "Bin %(bin)s is already assigned to "
                        "Pickup '%(pp1)s' / Drop-off '%(dp1)s'.\n"
                        "You cannot assign it again to "
                        "Pickup '%(pp2)s' / Drop-off '%(dp2)s'."
                    ) % {
                                              'bin': bin_rec.display_name,
                                              'pp1': prev_pp_name,
                                              'dp1': prev_dp_name,
                                              'pp2': pp_name,
                                              'dp2': dp_name,
                                          })

                # remember where this bin is used
                bin_usage_map[cid] = (pp_name, dp_name)
            # ---- END DUPLICATE VALIDATION -------------------------

            persistent_vals.append({
                'request_id': req.id,
                'pickup_point_id': pp_id,
                'dropoff_point_id': dp_id,
                'bin_lifted_ids': [(6, 0, line.bin_lifted_ids.ids)],
                'bin_dropped_ids': [(6, 0, line.bin_dropped_ids.ids)],
                'tank_ids': [(6, 0, line.tank_ids.ids)],
                'liters_collected': line.liters_collected,
                'liters_remaining': line.liters_remaining,
            })

            all_lifted |= line.bin_lifted_ids
            all_dropped |= line.bin_dropped_ids
            all_tanks |= line.tank_ids  # 🔹 collect all tanks
            total_liters_collected += line.liters_collected or 0.0

            # accumulate points for request M2Ms
            if pp_id:
                pickup_points |= self.env['pickup.point'].browse(pp_id)
            if dp_id:
                dropoff_points |= self.env['pickup.point'].browse(dp_id)

        if persistent_vals:
            self.env['waste.request.bin.line'].create(persistent_vals)

        # 🔹 sync lifted / dropped / tanks back to request
        req.bin_lifted_ids = [(6, 0, all_lifted.ids)]
        req.bin_dropped_ids = [(6, 0, all_dropped.ids)]
        req.tank_ids  = [(6, 0, all_tanks.ids)]

        # 🔹 sync total liters collected to the request (field must exist)
        req.liters_collected = total_liters_collected

        # sync pickup & drop-off points back to waste.service.request
        if pickup_points:
            req.pickup_point_ids = [(6, 0, pickup_points.ids)]
        else:
            req.pickup_point_ids = [(5, 0, 0)]

        if dropoff_points:
            req.dropoff_point_ids = [(6, 0, dropoff_points.ids)]
        else:
            req.dropoff_point_ids = [(5, 0, 0)]

        # ----------------------------------------------------
        # 🔹 NEW: RESERVE BINS FOR THIS REQUEST (placement)
        # ----------------------------------------------------
        if svc == 'placement of bins' and all_dropped:
            all_dropped.write({
                'reserved_request_id': req.id,
                # NOTE:
                # We only reserve here. Physical placement (status/inUse)
                # happens later in action_mark_done.
            })

        if svc == 'shunting of bins' and all_lifted:
            all_lifted.write({
                'reserved_request_id': req.id,
                # NOTE:
                # We only reserve here. Physical placement (status/inUse)
                # happens later in action_mark_done.
            })

        if svc == 'removal of bins' and all_lifted:
            all_lifted.write({
                'reserved_request_id': req.id,
                # NOTE:
                # We only reserve here. Physical placement (status/inUse)
                # happens later in action_mark_done.
            })

        if svc == 'waste collection & disposal' and all_lifted:
            all_lifted.write({
                'reserved_request_id': req.id,
                # NOTE:
                # We only reserve here. Physical placement (status/inUse)
                # happens later in action_mark_done.
            })

        # optional: behaviour for swapping of bins
        if svc == 'swapping of bins' and all_lifted:
            all_lifted.write({
                'reserved_request_id': req.id,
                # NOTE:
                # We only reserve here. Physical placement (status/inUse)
                # happens later in action_mark_done.
            })

            for line in self.line_ids:
                pp = line.pickup_point_id

                # lifted bins leave pickup point
                if line.bin_lifted_ids:
                    line.bin_lifted_ids.write({
                        'pickup_point_id': False,
                        'dropoff_point_id': False,
                        'inUse': False,
                    })

                # dropped bins go to pickup point
                if pp and line.bin_dropped_ids:
                    line.bin_dropped_ids.write({
                        'pickup_point_id': pp.id,
                        'partner_id': cust.id if cust else False,
                        'status': 'in_use',
                        'inUse': True,
                    })



        return {'type': 'ir.actions.act_window_close'}


class WasteAssignBinWizardLine(models.TransientModel):
    _name = 'waste.request.assign.bin.line.wizard'
    _description = 'Assign Bins Wizard Line'

    wizard_id = fields.Many2one(
        'waste.request.assign.bin.wizard',
        string="Wizard",
        required=True,
        ondelete='cascade',
    )

    request_id = fields.Many2one(
        'waste.service.request',
        string="Service Request",
    )

    svc_code = fields.Char(related='wizard_id.svc_code', store=False)
    partner_id = fields.Many2one(
        'res.partner',
        related='wizard_id.partner_id',
        store=False,
        readonly=True,
    )
    bin_type_id = fields.Many2one(
        'bin.type',
        related='wizard_id.bin_type_id',
        store=False,
        readonly=True,
    )

    waste_type_id = fields.Many2one(
        'waste.type',
        related='wizard_id.waste_type_id',
        store=False,
        readonly=True,
    )
    waste_type_name = fields.Char(
        related='wizard_id.waste_type_name',
        store=False,
        readonly=True,
    )

    # used in XML for bin_dropped visibility
    show_bin_dropped = fields.Boolean(
        related='wizard_id.show_bin_dropped',
        store=False,
        readonly=True,
    )

    pickup_point_id = fields.Many2one(
        'pickup.point',
        string="Pickup Point",
        domain="[('partner_id', '=', partner_id)]",
    )

    dropoff_point_id = fields.Many2one(
        'pickup.point',
        string="Drop-off Point",
        domain="[('partner_id', '=', partner_id)]",
    )

    # ------------------------------------------------------------
    # Dynamic domain: don't show bins that are already selected
    # on another wizard line
    # ------------------------------------------------------------
    @api.onchange('pickup_point_id', 'dropoff_point_id',
                  'bin_lifted_ids', 'bin_dropped_ids')
    def _onchange_bins_domain(self):
        """Exclude bins already used on other lines of this wizard."""
        self.ensure_one()
        if not self.wizard_id:
            return {}

        # other lines of the same wizard
        other_lines = self.wizard_id.line_ids - self

        used_bins = (
                other_lines.mapped('bin_lifted_ids') |
                other_lines.mapped('bin_dropped_ids')
        )

        return {
            'domain': {
                'bin_lifted_ids': [('id', 'not in', used_bins.ids)],
                'bin_dropped_ids': [('id', 'not in', used_bins.ids)],
            }
        }

    # bin_lifted_ids = fields.Many2many(
    #     'waste.container',
    #     'waste_assign_bin_wizard_line_lifted_rel',
    #     'line_id',
    #     'container_id',
    #     string="Bin Lifted",
    #     domain="""
    #         [
    #             ('partner_id', '=', customer_id),
    #             ('pickup_point_id', '=', pickup_point_id),
    #             ('status', 'in', ['in_use', 'un_use']),
    #             ('inUse', '=', True),
    #             ('container_type_id', '=', 'Bin'),
    #             ('reserved_request_id', '=', False),
    #             ('bin_type_id', 'in', ['6m³','9m³','11m³'])
    #         ]
    #     """,
    # )

    bin_lifted_ids = fields.Many2many(
        'waste.container',
        'waste_assign_bin_wizard_line_lifted_rel',
        'line_id',
        'container_id',
        string="Bin Lifted",
        domain="""
            [
                ('partner_id', '=', partner_id),
                ('pickup_point_id', '=', pickup_point_id),
                ('status', 'in', ['in_use', 'un_use']),
                ('inUse', '=', True),
                ('container_type_id', '=', 'Bin'),
                ('reserved_request_id', 'in', [False, request_id])
            ]
        """,
    )

    tank_ids = fields.Many2many(
        'waste.container',
        'waste_assign_tank_wizard_line_collect_rel',
        'line_id',
        'container_id',
        string="Tanks",
        domain="""
               [
                   ('partner_id', '=', partner_id),
                   ('pickup_point_id', '=', pickup_point_id),
                   ('status', 'in', ['in_use', 'un_use']),
                   ('inUse', '=', True),
                   ('container_type_id', '=', 'Tank'),
               ]
           """,
    )

    # bin_dropped_ids = fields.Many2many(
    #     'waste.container',
    #     'waste_assign_bin_wizard_line_dropped_rel',
    #     'line_id',
    #     'container_id',
    #     string="Bin Dropped",
    #     domain="""
    #         [
    #             ('partner_id', '=', False),
    #             ('pickup_point_id', '=', False),
    #             ('status', '=', 'intact'),
    #             ('inUse', '=', False),
    #             ('dropoff_point_id', '=', False),
    #             ('bin_type_id', 'in', ['6m³','9m³','11m³'])
    #         ]
    #     """,
    # )

    bin_dropped_ids = fields.Many2many(
        'waste.container',
        'waste_assign_bin_wizard_line_dropped_rel',
        'line_id',
        'container_id',
        string="Bin Dropped",
        domain="""
            [
                ('partner_id', '=', False),
                ('pickup_point_id', '=', False),
                ('status', '=', 'intact'),
                ('inUse', '=', False),
                ('dropoff_point_id', '=', False),
                ('reserved_request_id', '=', False),   
            ]
        """,
    )

    liters_collected = fields.Float(string="Liters Collected")
    liters_remaining = fields.Float(string="Liters Remaining")

    bin_duplicate_warning = fields.Char(
        string="Bin already used in this request",
        compute="_compute_bin_duplicate_warning",
        store=False,
    )

    @api.depends(
        'bin_lifted_ids',
        'bin_dropped_ids',
        'wizard_id.line_ids.bin_lifted_ids',
        'wizard_id.line_ids.bin_dropped_ids',
    )
    def _compute_bin_duplicate_warning(self):
        """If any bin on this line is also used on another line of the wizard,
        show a warning text.
        """
        for line in self:
            line.bin_duplicate_warning = False

            if not line.wizard_id:
                continue

            current_bins = set(line.bin_lifted_ids.ids + line.bin_dropped_ids.ids)
            if not current_bins:
                continue

            # other lines in same wizard
            other_lines = line.wizard_id.line_ids - line
            other_bins = set(
                other_lines.mapped('bin_lifted_ids').ids +
                other_lines.mapped('bin_dropped_ids').ids
            )

            dup_ids = current_bins.intersection(other_bins)
            if dup_ids:
                bins = self.env['waste.container'].browse(list(dup_ids))
                names = ", ".join(bins.mapped('display_name'))
                line.bin_duplicate_warning = _("Used on another line: %s") % names