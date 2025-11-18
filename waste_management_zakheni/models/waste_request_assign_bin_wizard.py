from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class WasteAssignBinWizard(models.TransientModel):
    _name = 'waste.request.assign.bin.wizard'
    _description = 'Assign Bins to Pickup Points Wizard'

    request_id = fields.Many2one(
        'waste.service.request',
        string="Service Request",
        required=True,
        readonly=True,
    )

    svc_code = fields.Char(compute="_compute_svc_metadata", store=False)
    customer_id = fields.Many2one('res.partner', compute="_compute_svc_metadata", store=False)
    bin_type_id = fields.Many2one('bin.type', compute="_compute_svc_metadata", store=False)

    shunt_to_id = fields.Many2one(
        'pickup.point',
        string="To Location (Drop-off Point)",
        domain="[('partner_id', '=', customer_id)]",
    )

    line_ids = fields.One2many(
        'waste.request.assign.bin.line.wizard',
        'wizard_id',
        string="Lines",
    )

    @api.depends('request_id')
    def _compute_svc_metadata(self):
        for wiz in self:
            req = wiz.request_id
            if not req:
                wiz.svc_code = ''
                wiz.customer_id = False
                wiz.bin_type_id = False
                continue

            code = (req.service_requested_id.code or '').lower() \
                if req.service_requested_id and hasattr(req.service_requested_id, 'code') \
                else (req.service_requested_id.display_name or '').strip().lower()

            wiz.svc_code = code
            wiz.customer_id = req.customer_id or req.partner_id
            wiz.bin_type_id = req.bin_type_id

    # ------------------------------------------------------------------
    # ✅ LOAD STORED LINES WHEN OPENING
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if not active_id:
            return res

        req = self.env['waste.service.request'].browse(active_id)
        res['request_id'] = req.id
        res['shunt_to_id'] = req.shunt_to_id.id if req.shunt_to_id else False

        # load persistent lines into wizard
        lines = []
        for l in req.bin_line_ids:
            lines.append((0, 0, {
                'pickup_point_id': l.pickup_point_id.id,
                'container_ids': [(6, 0, l.container_ids.ids)],
                'shunt_container_ids': [(6, 0, l.shunt_container_ids.ids)],
                'lifted_container_ids': [(6, 0, l.lifted_container_ids.ids)],
                'dropped_container_ids': [(6, 0, l.dropped_container_ids.ids)],
            }))

        if lines:
            res['line_ids'] = lines

        return res

    # ------------------------------------------------------------------
    # ✅ APPLY = SAVE LINES PERMANENTLY + SYNC REQUEST FIELDS
    # ------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        req = self.request_id
        svc = (self.svc_code or '').strip().lower()
        cust = self.customer_id or req.customer_id or req.partner_id

        # collect pickup points used in wizard lines
        pps = self.line_ids.mapped('pickup_point_id').filtered(lambda x: x)
        # save on request
        req.wizard_pickup_point_ids = [(6, 0, pps.ids)]

        # 1) Clear old persistent lines
        req.bin_line_ids.unlink()

        # 2) Recreate persistent lines from wizard
        persistent_vals = []
        for line in self.line_ids:
            persistent_vals.append({
                'request_id': req.id,
                'pickup_point_id': line.pickup_point_id.id,
                'container_ids': [(6, 0, line.container_ids.ids)],
                'shunt_container_ids': [(6, 0, line.shunt_container_ids.ids)],
                'lifted_container_ids': [(6, 0, line.lifted_container_ids.ids)],
                'dropped_container_ids': [(6, 0, line.dropped_container_ids.ids)],
            })
        if persistent_vals:
            self.env['waste.request.bin.line'].create(persistent_vals)

        # 3) Sync bins to request fields + bin/pickup mapping
        dropoff_bins = self.env['waste.container']
        shunt_bins = self.env['waste.container']
        lifted_bins = self.env['waste.container']
        dropped_bins = self.env['waste.container']

        for line in self.line_ids:
            pp = line.pickup_point_id

            if svc in ('placement of bins', 'removal of bins', 'waste collection & disposal'):
                dropoff_bins |= line.container_ids

                # placement assigns pickup now
                if svc == 'placement of bins' and pp:
                    line.container_ids.write({
                        'pickup_point_id': pp.id,
                        'customer_id': cust.id if cust else False,
                        'status': 'in_use',
                    })
                    if 'pickup_point_ids' in line.container_ids._fields:
                        for b in line.container_ids:
                            b.pickup_point_ids = [(4, pp.id)]

            elif svc == 'shunting of bins':
                shunt_bins |= line.shunt_container_ids
                req.shunt_to_id = self.shunt_to_id

                if self.shunt_to_id:
                    line.shunt_container_ids.write({
                        'pickup_point_id': self.shunt_to_id.id,
                        'customer_id': cust.id if cust else False,
                        'status': 'in_use',
                    })
                    if 'pickup_point_ids' in line.shunt_container_ids._fields:
                        for b in line.shunt_container_ids:
                            b.pickup_point_ids = [(4, self.shunt_to_id.id)]

            elif svc == 'swapping of bins':
                lifted_bins |= line.lifted_container_ids
                dropped_bins |= line.dropped_container_ids

                if pp and line.dropped_container_ids:
                    line.dropped_container_ids.write({
                        'pickup_point_id': pp.id,
                        'customer_id': cust.id if cust else False,
                        'status': 'in_use',
                    })
                    if 'pickup_point_ids' in line.dropped_container_ids._fields:
                        for b in line.dropped_container_ids:
                            b.pickup_point_ids = [(4, pp.id)]


        # write request M2Ms
        if svc in ('placement of bins', 'removal of bins', 'waste collection & disposal'):
            req.dropoff_container_ids = [(6, 0, dropoff_bins.ids)]
        elif svc == 'shunting of bins':
            req.shunt_container_ids = [(6, 0, shunt_bins.ids)]
        elif svc == 'swapping of bins':
            req.lifted_bin_ids = [(6, 0, lifted_bins.ids)]
            req.dropped_bin_ids = [(6, 0, dropped_bins.ids)]

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

    request_id = fields.Many2one('waste.service.request')

    svc_code = fields.Char(related='wizard_id.svc_code', store=False)

    pickup_point_id = fields.Many2one(
        'pickup.point',
        string="Pickup / Dropoff Point",
        required=True,
    )

    # bin_type_id = fields.Many2one('bin.type', related="wizard_id.bin_type_id", string="Bin Type")

    # pull bin type from wizard (same as request)
    bin_type_id = fields.Many2one(
        "bin.type",
        related="wizard_id.bin_type_id",
        string="Bin Type",
        readonly=True,
        store=False,
    )

    customer_id = fields.Many2one(
        'res.partner',
        related='wizard_id.customer_id',
        store=False,
        readonly=True,
        required=True,
    )

    # container_ids = fields.Many2many(
    #     'waste.container',
    #     'waste_assign_bin_wizard_line_cont_rel',
    #     'line_id', 'container_id',
    #     string="Containers",
    #     required=True,
    #     domain="[('pickup_point_id', '=', False),"
    #                    " ('customer_id', '=', False),"
    #                    " ('bin_type_id', '=', bin_type_id),"
    #                    " ('status', 'in', ('intact', 'un_use'))]",
    # )

    container_ids = fields.Many2many(
        'waste.container',
        'waste_assign_bin_wizard_line_cont_rel',
        'line_id', 'container_id',
        string="Containers",
        required=True,
        domain="""
            [
                ('pickup_point_id', '=', False),
                ('customer_id', '=', False),
                ('bin_type_id', '=', bin_type_id),
                ('status', 'in', ('intact', 'un_use'))
            ]
            """,
    )

    shunt_container_ids = fields.Many2many(
        'waste.container',
        'waste_assign_bin_wizard_line_shunt_rel',
        'line_id', 'container_id',
        string="Bins to Shunt",
        required=True,
        domain="""
               [
                   ('pickup_point_id', '=', pickup_point_id),
                   ('customer_id', '=', customer_id),
                   ('bin_type_id', '=', bin_type_id),
                   ('status', '!=', ('missing'))
               ]
               """,

    )

    lifted_container_ids = fields.Many2many(
        'waste.container',
        'waste_assign_bin_wizard_line_lifted_rel',
        'line_id', 'container_id',
        string="Lifted Bins",
        required=True,
        domain="""
                [
                    ('pickup_point_id', '=', pickup_point_id),
                    ('customer_id', '=', customer_id),
                    ('bin_type_id', '=', bin_type_id),
                    ('status', 'in', ('in_use','un_use'))
                ]
                """,
    )
    dropped_container_ids = fields.Many2many(
        'waste.container',
        'waste_assign_bin_wizard_line_dropped_rel',
        'line_id', 'container_id',
        string="Dropped Bins",
        required=True,
        domain="""
                [
                    ('pickup_point_id', '=', pickup_point_id),
                    ('customer_id', '=', customer_id),
                    ('bin_type_id', '=', bin_type_id),
                    ('status', 'in', ('broken','in_use','un_use'))
                ]
                """,
    )

    @api.onchange('pickup_point_id')
    def _onchange_pickup_point_id(self):
        for line in self:
            wiz = line.wizard_id
            svc = (wiz.svc_code or '').strip().lower()
            customer = wiz.customer_id
            bin_type = wiz.bin_type_id

            base_dom = []
            if bin_type:
                base_dom.append(('bin_type_id', '=', bin_type.id))

            domains = {}

            if svc == 'placement of bins':
                domains['container_ids'] = base_dom + [
                    ('pickup_point_id', '=', False),
                    ('customer_id', '=', False),
                    ('status', 'in', ['intact', 'un_use']),
                ]

            elif svc == 'removal of bins':
                domains['container_ids'] = base_dom + [
                    ('pickup_point_id', '=', line.pickup_point_id.id),
                    ('customer_id', '=', customer.id if customer else False),
                    ('status', 'in', ['intact', 'in_use', 'broken']),
                ]

            elif svc == 'waste collection & disposal':
                domains['container_ids'] = base_dom + [
                    ('pickup_point_id', '=', line.pickup_point_id.id),
                    ('customer_id', '=', customer.id if customer else False),
                    ('status', 'in', ['in_use', 'broken', 'un_use']),
                ]

            elif svc == 'shunting of bins':
                domains['shunt_container_ids'] = base_dom + [
                    ('pickup_point_id', '=', line.pickup_point_id.id),
                    ('customer_id', '=', customer.id if customer else False),
                ]

            elif svc == 'swapping of bins':
                domains['lifted_container_ids'] = base_dom + [
                    ('pickup_point_id', '=', line.pickup_point_id.id),
                    ('customer_id', '=', customer.id if customer else False),
                    ('status', 'in', ['broken', 'in_use', 'un_use']),
                ]
                domains['dropped_container_ids'] = base_dom + [
                    ('pickup_point_id', '=', False),
                    ('customer_id', '=', False),
                    ('status', 'in', ['intact']),
                ]

            return {'domain': domains}


# from odoo import models, fields, api, _
# from odoo.exceptions import ValidationError
#
#
# class WasteAssignBinWizard(models.TransientModel):
#     _name = 'waste.request.assign.bin.wizard'
#     _description = 'Assign Bins to Pickup Points Wizard'
#
#     request_id = fields.Many2one(
#         'waste.service.request',
#         string="Service Request",
#         required=True,
#         readonly=True,
#     )
#
#     @api.model
#     def default_get(self, fields_list):
#         res = super().default_get(fields_list)
#         active_id = self.env.context.get('active_id')
#         if not active_id:
#             return res
#
#         req = self.env['waste.service.request'].browse(active_id)
#         res['request_id'] = req.id
#         res['shunt_to_id'] = req.shunt_to_id.id if req.shunt_to_id else False
#
#         svc = (req.service_requested_id.code or '').lower() \
#             if req.service_requested_id and hasattr(req.service_requested_id, 'code') \
#             else (req.service_requested_id.display_name or '').strip().lower()
#
#         lines = []
#         default_pp = req.pickup_point_id
#
#         # ---------------- Placement / Removal / Collection ----------------
#         if svc in ('placement of bins', 'removal of bins', 'waste collection & disposal'):
#             grouped = {}
#             for b in req.dropoff_container_ids:
#                 pp = b.pickup_point_id or default_pp
#                 grouped.setdefault(pp, self.env['waste.container'])
#                 grouped[pp] |= b
#
#             for pp, bins in grouped.items():
#                 lines.append((0, 0, {
#                     'pickup_point_id': pp.id if pp else False,
#                     'container_ids': [(6, 0, bins.ids)],
#                 }))
#
#         # ---------------- Shunting ----------------
#         elif svc == 'shunting of bins':
#             grouped = {}
#             for b in req.shunt_container_ids:
#                 pp = b.pickup_point_id or default_pp
#                 grouped.setdefault(pp, self.env['waste.container'])
#                 grouped[pp] |= b
#
#             for pp, bins in grouped.items():
#                 lines.append((0, 0, {
#                     'pickup_point_id': pp.id if pp else False,
#                     'shunt_container_ids': [(6, 0, bins.ids)],
#                 }))
#
#         # ---------------- Swapping ----------------
#         elif svc == 'swapping of bins':
#             lines.append((0, 0, {
#                 'pickup_point_id': default_pp.id if default_pp else False,
#                 'lifted_container_ids': [(6, 0, req.lifted_bin_ids.ids)],
#                 'dropped_container_ids': [(6, 0, req.dropped_bin_ids.ids)],
#             }))
#
#         if lines:
#             res['line_ids'] = lines
#
#         return res
#
#     # @api.model
#     # def default_get(self, fields_list):
#     #     res = super().default_get(fields_list)
#     #     active_id = self.env.context.get('active_id')
#     #     if not active_id:
#     #         return res
#     #
#     #     req = self.env['waste.service.request'].browse(active_id)
#     #     res['request_id'] = req.id
#     #     res['shunt_to_id'] = req.shunt_to_id.id if req.shunt_to_id else False
#     #
#     #     svc = (req.service_requested_id.code or '').lower() \
#     #         if req.service_requested_id and hasattr(req.service_requested_id, 'code') \
#     #         else (req.service_requested_id.display_name or '').strip().lower()
#     #
#     #     lines = []
#     #     if svc in ('placement of bins', 'removal of bins', 'waste collection & disposal'):
#     #         # group existing bins by pickup point
#     #         grouped = {}
#     #         for b in req.dropoff_container_ids:
#     #             pp = b.pickup_point_id or req.pickup_point_id
#     #             grouped.setdefault(pp, self.env['waste.container'])
#     #             grouped[pp] |= b
#     #
#     #         for pp, bins in grouped.items():
#     #             lines.append((0, 0, {
#     #                 'pickup_point_id': pp.id if pp else False,
#     #                 'container_ids': [(6, 0, bins.ids)],
#     #             }))
#     #
#     #     elif svc == 'shunting of bins':
#     #         grouped = {}
#     #         for b in req.shunt_container_ids:
#     #             pp = b.pickup_point_id
#     #             grouped.setdefault(pp, self.env['waste.container'])
#     #             grouped[pp] |= b
#     #
#     #         for pp, bins in grouped.items():
#     #             lines.append((0, 0, {
#     #                 'pickup_point_id': pp.id if pp else False,
#     #                 'shunt_container_ids': [(6, 0, bins.ids)],
#     #             }))
#     #
#     #     elif svc == 'swapping of bins':
#     #         # one line for lifted, one for dropped
#     #         lines.append((0, 0, {
#     #             'pickup_point_id': req.pickup_point_id.id if req.pickup_point_id else False,
#     #             'lifted_container_ids': [(6, 0, req.lifted_bin_ids.ids)],
#     #             'dropped_container_ids': [(6, 0, req.dropped_bin_ids.ids)],
#     #         }))
#     #
#     #     if lines:
#     #         res['line_ids'] = lines
#     #
#     #     return res
#
#     # helper metadata
#     svc_code = fields.Char(compute="_compute_svc_metadata", store=False)
#     customer_id = fields.Many2one('res.partner', compute="_compute_svc_metadata", store=False)
#     bin_type_id = fields.Many2one('bin.type', compute="_compute_svc_metadata", store=False)
#
#     # ✅ NEW: To Location (Drop-off point for shunting)
#     shunt_to_id = fields.Many2one(
#         'pickup.point',
#         string="To Location (Drop-off Point)",
#         domain="[('partner_id', '=', customer_id)]",
#         help="For Shunting of Bins, select where bins will be moved to.",
#     )
#
#     line_ids = fields.One2many(
#         'waste.request.assign.bin.line.wizard',
#         'wizard_id',
#         string="Lines",
#     )
#
#     @api.depends('request_id')
#     def _compute_svc_metadata(self):
#         for wiz in self:
#             req = wiz.request_id
#             if not req:
#                 wiz.svc_code = ''
#                 wiz.customer_id = False
#                 wiz.bin_type_id = False
#                 continue
#
#             code = (req.service_requested_id.code or '').lower() \
#                 if req.service_requested_id and hasattr(req.service_requested_id, 'code') \
#                 else (req.service_requested_id.display_name or '').strip().lower()
#
#             wiz.svc_code = code
#             wiz.customer_id = req.customer_id or req.partner_id
#             wiz.bin_type_id = req.bin_type_id
#
#     @api.model
#     def default_get(self, fields_list):
#         res = super().default_get(fields_list)
#         active_id = self.env.context.get('active_id')
#         if active_id:
#             req = self.env['waste.service.request'].browse(active_id)
#             res['request_id'] = req.id
#
#             # ✅ preload shunt_to_id so it stays on wizard
#             res['shunt_to_id'] = req.shunt_to_id.id if req.shunt_to_id else False
#
#             # Optional: preload existing bins according to service
#             # (leave empty if you prefer clean)
#         return res
#
#     def action_confirm(self):
#         """Apply selections to request AND persist bin<->pickup point mapping."""
#         self.ensure_one()
#         req = self.request_id
#         svc = (self.svc_code or '').strip().lower()
#
#         cust = self.customer_id or req.customer_id or req.partner_id
#         dest_pps = req.pickup_point_ids  # related from SO (readonly list)
#         dest_pp_ids = dest_pps.ids
#         default_pp = req.pickup_point_id  # main pickup/dropoff point on request
#
#         dropoff_bins = self.env['waste.container']
#         shunt_bins = self.env['waste.container']
#         lifted_bins = self.env['waste.container']
#         dropped_bins = self.env['waste.container']
#
#         # ---------------------------------------------------------
#         # Collect bins per lines + SAVE pickup_point mapping
#         # ---------------------------------------------------------
#         for line in self.line_ids:
#             pp = line.pickup_point_id or default_pp  # line pickup point wins
#
#             # ========== PLACEMENT ==========
#             if svc == 'placement of bins':
#                 bins = line.container_ids
#                 dropoff_bins |= bins
#
#                 # ✅ Persist mapping immediately
#                 if pp:
#                     bins.write({
#                         'pickup_point_id': pp.id,
#                         'customer_id': cust.id if cust else False,
#                         'status': 'in_use',
#                     })
#                     # keep history in M2M if exists
#                     if 'pickup_point_ids' in bins._fields:
#                         for b in bins:
#                             b.pickup_point_ids = [(4, pp.id)]
#
#             # ========== REMOVAL ==========
#             elif svc == 'removal of bins':
#                 bins = line.container_ids
#                 dropoff_bins |= bins
#
#                 # ✅ Do NOT unassign here (your action_mark_done handles it)
#                 # But still keep mapping as-is; wizard just stores selection.
#
#             # ========== COLLECTION & DISPOSAL ==========
#             elif svc == 'waste collection & disposal':
#                 bins = line.container_ids
#                 dropoff_bins |= bins
#
#                 # ✅ Also don't unassign now; handled in action_mark_done.
#
#             # ========== SHUNTING ==========
#             elif svc == 'shunting of bins':
#                 bins = line.shunt_container_ids
#                 shunt_bins |= bins
#
#                 # ✅ Persist To Location on request
#                 req.shunt_to_id = self.shunt_to_id
#
#                 # ✅ Persist mapping now: move bins to shunt_to_id
#                 if self.shunt_to_id:
#                     bins.write({
#                         'pickup_point_id': self.shunt_to_id.id,
#                         'customer_id': cust.id if cust else False,
#                         'status': 'in_use',
#                     })
#                     if 'pickup_point_ids' in bins._fields:
#                         for b in bins:
#                             b.pickup_point_ids = [(4, self.shunt_to_id.id)]
#
#             # ========== SWAPPING ==========
#             elif svc == 'swapping of bins':
#                 lifted = line.lifted_container_ids
#                 dropped = line.dropped_container_ids
#
#                 lifted_bins |= lifted
#                 dropped_bins |= dropped
#
#                 # ✅ Dropped bins become new bins at that pickup/dropoff point
#                 if pp and dropped:
#                     dropped.write({
#                         'pickup_point_id': pp.id,
#                         'customer_id': cust.id if cust else False,
#                         'status': 'in_use',
#                     })
#                     if 'pickup_point_ids' in dropped._fields:
#                         for b in dropped:
#                             b.pickup_point_ids = [(4, pp.id)]
#
#                 # ✅ Lifted bins stay as-is now; action_mark_done clears them later.
#
#         # ---------------------------------------------------------
#         # Save bins onto request fields (same as before)
#         # ---------------------------------------------------------
#         if svc in ('placement of bins', 'removal of bins', 'waste collection & disposal'):
#             req.dropoff_container_ids = [(6, 0, dropoff_bins.ids)]
#
#         elif svc == 'shunting of bins':
#             req.shunt_container_ids = [(6, 0, shunt_bins.ids)]
#
#         elif svc == 'swapping of bins':
#             req.lifted_bin_ids = [(6, 0, lifted_bins.ids)]
#             req.dropped_bin_ids = [(6, 0, dropped_bins.ids)]
#
#         return {'type': 'ir.actions.act_window_close'}
#
#     # def action_confirm(self):
#     #     """Apply selections to request & persist shunt_to_id."""
#     #     self.ensure_one()
#     #     req = self.request_id
#     #     svc = (self.svc_code or '').strip().lower()
#     #
#     #     dropoff_bins = self.env['waste.container']
#     #     shunt_bins = self.env['waste.container']
#     #     lifted_bins = self.env['waste.container']
#     #     dropped_bins = self.env['waste.container']
#     #
#     #     for line in self.line_ids:
#     #         if svc in ('placement of bins', 'removal of bins', 'waste collection & disposal'):
#     #             dropoff_bins |= line.container_ids
#     #         elif svc == 'shunting of bins':
#     #             shunt_bins |= line.shunt_container_ids
#     #         elif svc == 'swapping of bins':
#     #             lifted_bins |= line.lifted_container_ids
#     #             dropped_bins |= line.dropped_container_ids
#     #
#     #     if svc in ('placement of bins', 'removal of bins', 'waste collection & disposal'):
#     #         req.dropoff_container_ids = [(6, 0, dropoff_bins.ids)]
#     #
#     #     elif svc == 'shunting of bins':
#     #         # ✅ Persist To Location on request
#     #         req.shunt_to_id = self.shunt_to_id
#     #
#     #         req.shunt_container_ids = [(6, 0, shunt_bins.ids)]
#     #
#     #     elif svc == 'swapping of bins':
#     #         req.lifted_bin_ids = [(6, 0, lifted_bins.ids)]
#     #         req.dropped_bin_ids = [(6, 0, dropped_bins.ids)]
#     #
#     #     return {'type': 'ir.actions.act_window_close'}
#
#
# class WasteAssignBinWizardLine(models.TransientModel):
#     _name = 'waste.request.assign.bin.line.wizard'
#     _description = 'Assign Bins Wizard Line'
#
#     wizard_id = fields.Many2one(
#         'waste.request.assign.bin.wizard',
#         string="Wizard",
#         required=True,
#         ondelete='cascade',
#     )
#
#     svc_code = fields.Char(
#         related='wizard_id.svc_code',
#         store=False,
#         string="Service Code",
#     )
#
#     pickup_point_id = fields.Many2one(
#         'pickup.point',
#         string="Pickup / Dropoff Point",
#         help="Pickup point (also works as dropoff point).",
#     )
#
#     customer_id = fields.Many2one(
#         'res.partner',
#         related='wizard_id.customer_id',
#         store=False,
#         readonly=True,
#         string="Customer",
#     )
#
#     # For Placement / Removal / Collection
#     container_ids = fields.Many2many(
#         'waste.container',
#         'waste_assign_bin_wizard_line_cont_rel',
#         'line_id',
#         'container_id',
#         string="Containers",
#     )
#
#     # For Shunting
#     shunt_container_ids = fields.Many2many(
#         'waste.container',
#         'waste_assign_bin_wizard_line_shunt_rel',
#         'line_id',
#         'container_id',
#         string="Shunt Containers",
#     )
#
#     # For Swapping
#     lifted_container_ids = fields.Many2many(
#         'waste.container',
#         'waste_assign_bin_wizard_line_lifted_rel',
#         'line_id',
#         'container_id',
#         string="Lifted Bins",
#     )
#     dropped_container_ids = fields.Many2many(
#         'waste.container',
#         'waste_assign_bin_wizard_line_dropped_rel',
#         'line_id',
#         'container_id',
#         string="Dropped Bins",
#     )
#
#     @api.onchange('pickup_point_id')
#     def _onchange_pickup_point_id(self):
#         """Apply your domain rules based on svc_code, bin_type_id, pickup_point, customer."""
#         for line in self:
#             wiz = line.wizard_id
#             svc = (wiz.svc_code or '').strip().lower()
#             customer = wiz.customer_id
#             bin_type = wiz.bin_type_id
#
#             base_dom = []
#             if bin_type:
#                 base_dom.append(('bin_type_id', '=', bin_type.id))
#
#             domains = {}
#
#             # ---------- Placement of Bins ----------
#             if svc == 'placement of bins':
#                 # free intact/un_use bins; no pickup, no customer
#                 domains['container_ids'] = base_dom + [
#                     ('pickup_point_id', '=', False),
#                     ('customer_id', '=', False),
#                     ('status', 'in', ['intact', 'un_use']),
#                 ]
#
#             # ---------- Removal of Bins ----------
#             elif svc == 'removal of bins':
#                 domains['container_ids'] = base_dom + [
#                     ('pickup_point_id', '=',
#                      line.pickup_point_id.id if line.pickup_point_id else False),
#                     ('customer_id', '=',
#                      customer.id if customer else False),
#                     ('status', 'in', ['intact', 'in_use', 'broken']),
#                 ]
#
#             # ---------- Waste Collection & Disposal ----------
#             elif svc == 'waste collection & disposal':
#                 domains['container_ids'] = base_dom + [
#                     ('pickup_point_id', '=',
#                      line.pickup_point_id.id if line.pickup_point_id else False),
#                     ('customer_id', '=',
#                      customer.id if customer else False),
#                     ('status', 'in', ['in_use', 'broken', 'un_use']),
#                 ]
#
#             # ---------- Shunting of Bins ----------
#             elif svc == 'shunting of bins':
#                 domains['shunt_container_ids'] = base_dom + [
#                     ('pickup_point_id', '=',
#                      line.pickup_point_id.id if line.pickup_point_id else False),
#                     ('customer_id', '=',
#                      customer.id if customer else False),
#                 ]
#
#             # ---------- Swapping of Bins ----------
#             elif svc == 'swapping of bins':
#                 # lifted: from pickup+customer, statuses broken/in_use/un_use
#                 domains['lifted_container_ids'] = base_dom + [
#                     ('pickup_point_id', '=',
#                      line.pickup_point_id.id if line.pickup_point_id else False),
#                     ('customer_id', '=',
#                      customer.id if customer else False),
#                     ('status', 'in', ['broken', 'in_use', 'un_use']),
#                 ]
#                 # dropped: intact free bins
#                 domains['dropped_container_ids'] = base_dom + [
#                     ('pickup_point_id', '=', False),
#                     ('customer_id', '=', False),
#                     ('status', 'in', ['intact']),
#                 ]
#
#             return {'domain': domains}
#
#
#
#
#
# # from odoo import models, fields, api
# #
# #
# # class WasteAssignBinWizard(models.TransientModel):
# #     _name = 'waste.request.assign.bin.wizard'
# #     _description = 'Assign Bins to Pickup Points Wizard'
# #
# #     request_id = fields.Many2one(
# #         'waste.service.request',
# #         string="Service Request",
# #         required=True,
# #         readonly=True,
# #     )
# #
# #     # Helper fields derived from request (NO Selection, only Many2one + Char)
# #     svc_code = fields.Char(
# #         string="Service Code",
# #         compute="_compute_svc_metadata",
# #         store=False,
# #     )
# #     customer_id = fields.Many2one(
# #         'res.partner',
# #         string="Customer",
# #         compute="_compute_svc_metadata",
# #         store=False,
# #     )
# #     bin_type_id = fields.Many2one(
# #         'bin.type',  # your existing field on waste.service.request
# #         string="Bin Type",
# #         compute="_compute_svc_metadata",
# #         store=False,
# #     )
# #
# #     line_ids = fields.One2many(
# #         'waste.request.assign.bin.line.wizard',
# #         'wizard_id',
# #         string="Lines",
# #     )
# #
# #     @api.depends('request_id')
# #     def _compute_svc_metadata(self):
# #         """Get svc_code (same as in action_mark_done), customer and bin_type."""
# #         for wiz in self:
# #             code = ''
# #             customer = False
# #             bin_type = False
# #             if wiz.request_id:
# #                 # same logic you already use in action_mark_done
# #                 code = (wiz.request_id.service_requested_id.code or '').lower() \
# #                     if wiz.request_id.service_requested_id and hasattr(wiz.request_id.service_requested_id, 'code') \
# #                     else (wiz.request_id.service_requested_id.display_name or '').strip().lower()
# #                 customer = wiz.request_id.customer_id or wiz.request_id.partner_id
# #                 bin_type = wiz.request_id.bin_type_id
# #             wiz.svc_code = code
# #             wiz.customer_id = customer
# #             wiz.bin_type_id = bin_type
# #
# #     @api.model
# #     def default_get(self, fields_list):
# #         res = super().default_get(fields_list)
# #         active_id = self.env.context.get('active_id')
# #         if active_id:
# #             res['request_id'] = active_id
# #         return res
# #
# #     def action_confirm(self):
# #         """Push selected bins back to the correct M2M fields on the request."""
# #         self.ensure_one()
# #         req = self.request_id
# #         svc = (self.svc_code or '').strip().lower()
# #
# #         dropoff_bins = self.env['waste.container']
# #         shunt_bins = self.env['waste.container']
# #         lifted_bins = self.env['waste.container']
# #         dropped_bins = self.env['waste.container']
# #
# #         for line in self.line_ids:
# #             # Placement / Removal / Waste Collection & Disposal use container_ids
# #             if svc in ('placement of bins',
# #                        'removal of bins',
# #                        'waste collection & disposal'):
# #                 dropoff_bins |= line.container_ids
# #
# #             # Shunting of Bins uses shunt_container_ids
# #             elif svc == 'shunting of bins':
# #                 shunt_bins |= line.shunt_container_ids
# #
# #             # Swapping of Bins uses lifted + dropped
# #             elif svc == 'swapping of bins':
# #                 lifted_bins |= line.lifted_container_ids
# #                 dropped_bins |= line.dropped_container_ids
# #
# #         # --- write back to request fields ---
# #
# #         if svc in ('placement of bins', 'removal of bins', 'waste collection & disposal'):
# #             req.dropoff_container_ids = [(6, 0, dropoff_bins.ids)]
# #
# #         elif svc == 'shunting of bins':
# #             req.shunt_container_ids = [(6, 0, shunt_bins.ids)]
# #
# #         elif svc == 'swapping of bins':
# #             req.lifted_bin_ids = [(6, 0, lifted_bins.ids)]
# #             req.dropped_bin_ids = [(6, 0, dropped_bins.ids)]
# #
# #         # your existing action_mark_done will use these as usual
# #         return {'type': 'ir.actions.act_window_close'}
# #
# #
# # class WasteAssignBinWizardLine(models.TransientModel):
# #     _name = 'waste.request.assign.bin.line.wizard'
# #     _description = 'Assign Bins Wizard Line'
# #
# #     wizard_id = fields.Many2one(
# #         'waste.request.assign.bin.wizard',
# #         string="Wizard",
# #         required=True,
# #         ondelete='cascade',
# #     )
# #
# #     svc_code = fields.Char(
# #         related='wizard_id.svc_code',
# #         store=False,
# #         string="Service Code",
# #     )
# #
# #     pickup_point_id = fields.Many2one(
# #         'pickup.point',
# #         string="Pickup / Dropoff Point",
# #         help="Pickup point (also works as dropoff point).",
# #     )
# #
# #     # For Placement / Removal / Collection
# #     container_ids = fields.Many2many(
# #         'waste.container',
# #         'waste_assign_bin_wizard_line_cont_rel',
# #         'line_id',
# #         'container_id',
# #         string="Containers",
# #     )
# #
# #     # For Shunting
# #     shunt_container_ids = fields.Many2many(
# #         'waste.container',
# #         'waste_assign_bin_wizard_line_shunt_rel',
# #         'line_id',
# #         'container_id',
# #         string="Shunt Containers",
# #     )
# #
# #     # For Swapping
# #     lifted_container_ids = fields.Many2many(
# #         'waste.container',
# #         'waste_assign_bin_wizard_line_lifted_rel',
# #         'line_id',
# #         'container_id',
# #         string="Lifted Bins",
# #     )
# #     dropped_container_ids = fields.Many2many(
# #         'waste.container',
# #         'waste_assign_bin_wizard_line_dropped_rel',
# #         'line_id',
# #         'container_id',
# #         string="Dropped Bins",
# #     )
# #
# #     @api.onchange('pickup_point_id')
# #     def _onchange_pickup_point_id(self):
# #         """Apply your domain rules based on svc_code, bin_type_id, pickup_point, customer."""
# #         for line in self:
# #             wiz = line.wizard_id
# #             svc = (wiz.svc_code or '').strip().lower()
# #             customer = wiz.customer_id
# #             bin_type = wiz.bin_type_id
# #
# #             base_dom = []
# #             if bin_type:
# #                 base_dom.append(('bin_type_id', '=', bin_type.id))
# #
# #             domains = {}
# #
# #             # ---------- Placement of Bins ----------
# #             if svc == 'placement of bins':
# #                 # free intact/un_use bins; no pickup, no customer
# #                 domains['container_ids'] = base_dom + [
# #                     ('pickup_point_id', '=', False),
# #                     ('customer_id', '=', False),
# #                     ('status', 'in', ['intact', 'un_use']),
# #                 ]
# #
# #             # ---------- Removal of Bins ----------
# #             elif svc == 'removal of bins':
# #                 domains['container_ids'] = base_dom + [
# #                     ('pickup_point_id', '=',
# #                      line.pickup_point_id.id if line.pickup_point_id else False),
# #                     ('customer_id', '=',
# #                      customer.id if customer else False),
# #                     ('status', 'in', ['intact', 'in_use', 'broken']),
# #                 ]
# #
# #             # ---------- Waste Collection & Disposal ----------
# #             elif svc == 'waste collection & disposal':
# #                 domains['container_ids'] = base_dom + [
# #                     ('pickup_point_id', '=',
# #                      line.pickup_point_id.id if line.pickup_point_id else False),
# #                     ('customer_id', '=',
# #                      customer.id if customer else False),
# #                     ('status', 'in', ['in_use', 'broken', 'un_use']),
# #                 ]
# #
# #             # ---------- Shunting of Bins ----------
# #             elif svc == 'shunting of bins':
# #                 domains['shunt_container_ids'] = base_dom + [
# #                     ('pickup_point_id', '=',
# #                      line.pickup_point_id.id if line.pickup_point_id else False),
# #                     ('customer_id', '=',
# #                      customer.id if customer else False),
# #                 ]
# #
# #             # ---------- Swapping of Bins ----------
# #             elif svc == 'swapping of bins':
# #                 # lifted: from pickup+customer, statuses broken/in_use/un_use
# #                 domains['lifted_container_ids'] = base_dom + [
# #                     ('pickup_point_id', '=',
# #                      line.pickup_point_id.id if line.pickup_point_id else False),
# #                     ('customer_id', '=',
# #                      customer.id if customer else False),
# #                     ('status', 'in', ['broken', 'in_use', 'un_use']),
# #                 ]
# #                 # dropped: intact free bins
# #                 domains['dropped_container_ids'] = base_dom + [
# #                     ('pickup_point_id', '=', False),
# #                     ('customer_id', '=', False),
# #                     ('status', 'in', ['intact']),
# #                 ]
# #
# #             return {'domain': domains}
# #
#
# # # from odoo import models, fields, api, _
# # #
# # # class WasteAssignBinWizard(models.TransientModel):
# # #     _name = 'waste.request.assign.bin.wizard'
# # #     _description = 'Assign Bins to Pickup Points Wizard'
# # #
# # #     request_id = fields.Many2one(
# # #         'waste.service.request',
# # #         string="Service Request",
# # #         required=True,
# # #         readonly=True,
# # #     )
# # #
# # #     line_ids = fields.One2many(
# # #         'waste.request.assign.bin.line.wizard',
# # #         'wizard_id',
# # #         string="Lines",
# # #     )
# # #
# # #     @api.model
# # #     def default_get(self, fields_list):
# # #         """Pre-fill wizard lines from existing request lines."""
# # #         res = super().default_get(fields_list)
# # #         active_id = self.env.context.get('active_id') or res.get('request_id')
# # #         if active_id and 'request_id' in fields_list:
# # #             res['request_id'] = active_id
# # #
# # #         if active_id and 'line_ids' in fields_list:
# # #             req = self.env['waste.service.request'].browse(active_id)
# # #             lines_vals = []
# # #             for line in req.bin_line_ids:
# # #                 lines_vals.append((
# # #                     0, 0, {
# # #                         'pickup_point_id': line.pickup_point_id.id,
# # #                         'container_ids': [(6, 0, line.container_ids.ids)],
# # #                     }
# # #                 ))
# # #             if lines_vals:
# # #                 res['line_ids'] = lines_vals
# # #
# # #         return res
# # #
# # #     def action_confirm(self):
# # #         """Write wizard content back to persistent model."""
# # #         self.ensure_one()
# # #         RequestBinLine = self.env['waste.request.bin.line']
# # #
# # #         # Clear existing mappings for this request
# # #         self.request_id.bin_line_ids.unlink()
# # #
# # #         # Create new lines based on wizard input
# # #         for line in self.line_ids:
# # #             if not line.pickup_point_id or not line.container_ids:
# # #                 continue
# # #             RequestBinLine.create({
# # #                 'request_id': self.request_id.id,
# # #                 'pickup_point_id': line.pickup_point_id.id,
# # #                 'container_ids': [(6, 0, line.container_ids.ids)],
# # #             })
# # #
# # #         return {'type': 'ir.actions.act_window_close'}
