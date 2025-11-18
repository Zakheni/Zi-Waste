from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class WasteWorksheetAssignBinWizard(models.TransientModel):
    _name = "waste.worksheet.assign.bin.wizard"
    _description = "Assign Bins Wizard (from Worksheet)"

    worksheet_id = fields.Many2one(
        "waste.worksheet",
        string="Worksheet",
        required=True,
        readonly=True,
    )

    request_id = fields.Many2one(
        "waste.service.request",
        string="Service Request",
        related="worksheet_id.service_request_id",
        store=False,
        readonly=True,
    )

    # helper metadata (same as request wizard)
    svc_code = fields.Char(compute="_compute_svc_metadata", store=False)
    customer_id = fields.Many2one("res.partner", compute="_compute_svc_metadata", store=False)
    bin_type_id = fields.Many2one("bin.type", compute="_compute_svc_metadata", store=False)

    shunt_to_id = fields.Many2one(
        "pickup.point",
        string="To Location (Drop-off Point)",
        domain="[('partner_id', '=', customer_id)]",
        help="For Shunting of Bins, select where bins will be moved to.",
    )

    line_ids = fields.One2many(
        "waste.worksheet.assign.bin.line.wizard",
        "wizard_id",
        string="Lines",
    )

    # ---------------------------------------------------------
    # Metadata
    # ---------------------------------------------------------
    @api.depends("worksheet_id")
    def _compute_svc_metadata(self):
        for wiz in self:
            req = wiz.request_id
            if not req:
                wiz.svc_code = ""
                wiz.customer_id = False
                wiz.bin_type_id = False
                continue

            code = (req.service_requested_id.code or "").lower() \
                if req.service_requested_id and hasattr(req.service_requested_id, "code") \
                else (req.service_requested_id.display_name or "").strip().lower()

            wiz.svc_code = code
            wiz.customer_id = req.customer_id or req.partner_id
            wiz.bin_type_id = req.bin_type_id

    # ---------------------------------------------------------
    # Defaults: open from worksheet smart button
    # ---------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_id = self.env.context.get("active_id")
        active_model = self.env.context.get("active_model")

        if active_model == "waste.worksheet" and active_id:
            ws = self.env["waste.worksheet"].browse(active_id)
            res["worksheet_id"] = ws.id

            req = ws.service_request_id
            if req:
                # keep shunt_to_id on wizard
                res["shunt_to_id"] = req.shunt_to_id.id if req.shunt_to_id else False

                # preload lines from persistent request lines
                lines_vals = []
                for l in req.bin_line_ids:
                    lines_vals.append((0, 0, {
                        "pickup_point_id": l.pickup_point_id.id,
                        "container_ids": [(6, 0, l.container_ids.ids)],
                        "shunt_container_ids": [(6, 0, l.shunt_container_ids.ids)],
                        "lifted_container_ids": [(6, 0, l.lifted_container_ids.ids)],
                        "dropped_container_ids": [(6, 0, l.dropped_container_ids.ids)],
                    }))
                res["line_ids"] = lines_vals

        return res

    # ---------------------------------------------------------
    # Apply: write to request (persistent)
    # ---------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        req = self.request_id
        if not req:
            return {"type": "ir.actions.act_window_close"}

        svc = (self.svc_code or "").strip().lower()

        # gather bins for request-level M2M
        dropoff_bins = self.env["waste.container"]
        shunt_bins = self.env["waste.container"]
        lifted_bins = self.env["waste.container"]
        dropped_bins = self.env["waste.container"]

        # -----------------------------------------------------
        # 1) Replace persistent request bin_line_ids
        # -----------------------------------------------------
        req.bin_line_ids.unlink()

        new_lines = []
        for line in self.line_ids:
            if not line.pickup_point_id:
                continue

            vals = {
                "request_id": req.id,
                "pickup_point_id": line.pickup_point_id.id,
                "container_ids": [(6, 0, line.container_ids.ids)],
                "shunt_container_ids": [(6, 0, line.shunt_container_ids.ids)],
                "lifted_container_ids": [(6, 0, line.lifted_container_ids.ids)],
                "dropped_container_ids": [(6, 0, line.dropped_container_ids.ids)],
            }
            new_lines.append((0, 0, vals))

            # collect for request container M2Ms
            if svc in ("placement of bins", "removal of bins", "waste collection & disposal"):
                dropoff_bins |= line.container_ids
            elif svc == "shunting of bins":
                shunt_bins |= line.shunt_container_ids
            elif svc == "swapping of bins":
                lifted_bins |= line.lifted_container_ids
                dropped_bins |= line.dropped_container_ids

        req.write({"bin_line_ids": new_lines})

        # -----------------------------------------------------
        # 2) Update request container M2Ms
        # -----------------------------------------------------
        if svc in ("placement of bins", "removal of bins", "waste collection & disposal"):
            req.dropoff_container_ids = [(6, 0, dropoff_bins.ids)]
        elif svc == "shunting of bins":
            req.shunt_to_id = self.shunt_to_id
            req.shunt_container_ids = [(6, 0, shunt_bins.ids)]
        elif svc == "swapping of bins":
            req.lifted_bin_ids = [(6, 0, lifted_bins.ids)]
            req.dropped_bin_ids = [(6, 0, dropped_bins.ids)]

        # -----------------------------------------------------
        # 3) Update wizard_pickup_point_ids on request
        #    (silently cap to 10)
        # -----------------------------------------------------
        pickup_points = self.line_ids.mapped("pickup_point_id")
        pickup_points = pickup_points[:10]
        req.wizard_pickup_point_ids = [(6, 0, pickup_points.ids)]

        return {"type": "ir.actions.act_window_close"}


class WasteWorksheetAssignBinWizardLine(models.TransientModel):
    _name = "waste.worksheet.assign.bin.line.wizard"
    _description = "Assign Bins Wizard Line (Worksheet)"

    wizard_id = fields.Many2one(
        "waste.worksheet.assign.bin.wizard",
        required=True,
        ondelete="cascade",
    )

    svc_code = fields.Char(related="wizard_id.svc_code", store=False)
    customer_id = fields.Many2one(related="wizard_id.customer_id", store=False, readonly=True)
    bin_type_id = fields.Many2one(related="wizard_id.bin_type_id", store=False, readonly=True)

    pickup_point_id = fields.Many2one(
        "pickup.point",
        string="Pickup / Dropoff Point",
        help="Pickup point (also used as dropoff).",
        domain="[('partner_id', '=', customer_id)]",
    )

    # Placement / Removal / Collection
    container_ids = fields.Many2many(
        "waste.container",
        "waste_ws_assign_line_cont_rel",
        "line_id",
        "container_id",
        string="Containers",
        domain="""
                [
                    ('pickup_point_id', '=', False),
                    ('customer_id', '=', False),
                    ('bin_type_id', '=', bin_type_id),
                    ('status', 'in', ('intact', 'un_use'))
                ]
                """,
    )

    # Shunting
    shunt_container_ids = fields.Many2many(
        "waste.container",
        "waste_ws_assign_line_shunt_rel",
        "line_id",
        "container_id",
        string="Bins to Shunt",
        domain="""
                  [
                      ('pickup_point_id', '=', pickup_point_id),
                      ('customer_id', '=', customer_id),
                      ('bin_type_id', '=', bin_type_id),
                      ('status', '!=', ('missing'))
                  ]
                  """,
    )

    # Swapping
    lifted_container_ids = fields.Many2many(
        "waste.container",
        "waste_ws_assign_line_lifted_rel",
        "line_id",
        "container_id",
        string="Lifted Bins",
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
        "waste.container",
        "waste_ws_assign_line_dropped_rel",
        "line_id",
        "container_id",
        string="Dropped Bins",
        domain="""
                   [
                       ('pickup_point_id', '=', pickup_point_id),
                       ('customer_id', '=', customer_id),
                       ('bin_type_id', '=', bin_type_id),
                       ('status', 'in', ('broken','in_use','un_use'))
                   ]
                   """,
    )

    # ---------------------------------------------------------
    # Domains per service type (same rules you gave)
    # ---------------------------------------------------------
    @api.onchange("pickup_point_id")
    def _onchange_pickup_point_id(self):
        for line in self:
            wiz = line.wizard_id
            svc = (wiz.svc_code or "").strip().lower()
            customer = wiz.customer_id
            bin_type = wiz.bin_type_id

            base_dom = []
            if bin_type:
                base_dom.append(("bin_type_id", "=", bin_type.id))

            domains = {}

            # Placement = free intact/un_use bins
            if svc == "placement of bins":
                domains["container_ids"] = base_dom + [
                    ("pickup_point_id", "=", False),
                    ("customer_id", "=", False),
                    ("status", "in", ["intact", "un_use"]),
                ]

            # Removal = bins at pickup point for customer
            elif svc == "removal of bins":
                domains["container_ids"] = base_dom + [
                    ("pickup_point_id", "=", line.pickup_point_id.id if line.pickup_point_id else False),
                    ("customer_id", "=", customer.id if customer else False),
                    ("status", "in", ["intact", "in_use", "broken"]),
                ]

            # Waste collection & disposal
            elif svc == "waste collection & disposal":
                domains["container_ids"] = base_dom + [
                    ("pickup_point_id", "=", line.pickup_point_id.id if line.pickup_point_id else False),
                    ("customer_id", "=", customer.id if customer else False),
                    ("status", "in", ["in_use", "broken", "un_use"]),
                ]

            # Shunting = any bins at pickup point for customer
            elif svc == "shunting of bins":
                domains["shunt_container_ids"] = base_dom + [
                    ("pickup_point_id", "=", line.pickup_point_id.id if line.pickup_point_id else False),
                    ("customer_id", "=", customer.id if customer else False),
                ]

            # Swapping
            elif svc == "swapping of bins":
                domains["lifted_container_ids"] = base_dom + [
                    ("pickup_point_id", "=", line.pickup_point_id.id if line.pickup_point_id else False),
                    ("customer_id", "=", customer.id if customer else False),
                    ("status", "in", ["broken", "in_use", "un_use"]),
                ]
                domains["dropped_container_ids"] = base_dom + [
                    ("pickup_point_id", "=", False),
                    ("customer_id", "=", False),
                    ("status", "in", ["intact"]),
                ]

            return {"domain": domains}
