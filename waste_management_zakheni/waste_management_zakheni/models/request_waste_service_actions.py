"""Document, worksheet, bin, and sales UI actions for waste manifests."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessDenied


class WasteServiceRequestActions(models.Model):
    """Mixin: smart buttons, wizards, and document popups."""

    _inherit = 'waste.service.request'

    def action_cancelled(self):
        """Cancel manifest and open the rejection reason wizard."""
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
                'default_employee_email_id': self.employee_email_id.id,
            },
        }

    def action_amend(self):
        """Open the amend-comment wizard for a delivered service."""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Enter Amend Comment',
            'res_model': 'amend.service.request.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
                'default_employee_manager_id': self.employee_manager_id.id,
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


    def action_open_manifest_document(self):
        """Open popup to upload or view the manifest document."""
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
        """Open popup to upload or view the weighbridge slip."""
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
        """Open popup to upload or view the safety certificate."""
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
    @api.depends('worksheet_ids')
    def _compute_worksheets_count(self):
        """Count worksheets linked to this manifest."""
        for rec in self:
            rec.worksheet_count = len(rec.worksheet_ids)

    @api.depends("worksheet_ids")
    def _compute_latest_worksheet(self):
        """Mirror fields from the most recent worksheet onto the manifest."""
        for rec in self:
            if rec.worksheet_ids:
                latest = rec.worksheet_ids[-1]  # last created schedule
                rec.latest_worksheet_arrival_time = latest.arrival_time
                rec.latest_worksheet_kilometers = latest.kilometers
                rec.latest_worksheet_return_date = latest.return_date
                rec.latest_worksheet_unit_of_measure = latest.unit_of_measure
                # rec.latest_worksheet_quantity_collected = latest.quantity_collected
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
                # rec.latest_worksheet_quantity_collected = False
                rec.latest_worksheet_driver_signature = False
                rec.latest_worksheet_manifest_document = False
                rec.latest_worksheet_weighbridge_slip = False
                rec.latest_worksheet_safety_certificate = False
                rec.latest_worksheet_notes_html = False  # 🔹 NEW

    def action_view_worksheet(self):
        """Open the list/form view of linked worksheets."""
        return {
            "type": "ir.actions.act_window",
            "name": "Worksheet",
            "res_model": "waste.worksheet",
            "view_mode": "tree,form",
            "target": "current",
            "domain": [("service_request_id", "=", self.id)],
            "context": {"default_service_request_id": self.id},
        }

    @api.depends('extra_product_line_ids')
    def _compute_extra_product_count(self):
        """Count extra product lines awaiting push to the sale order."""
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
        """Build a readable summary of bins/tanks per pickup point."""
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

    @api.depends('pickup_point_ids', 'wizard_pickup_point_ids')
    def _compute_wizard_pickup_point_count(self):
        """Count pickup points shown on the assign-bins stat button."""
        for rec in self:
            points = rec.wizard_pickup_point_ids or rec.pickup_point_ids
            rec.wizard_pickup_point_count = len(points)

    @api.depends(
        "bin_line_ids.bin_lifted_ids",
        "bin_line_ids.bin_dropped_ids",
    )
    def _compute_bin_line_count(self):
        """Count bins involved based on the selected service type."""
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
        """Launch the assign-bins wizard for this manifest."""
        self.ensure_one()
        action = self.env.ref('waste_management_zakheni.action_waste_assign_bin_wizard').sudo().read()[0]
        action['context'] = {
            'default_request_id': self.id,
            'active_id': self.id,
            'active_model': self._name,
        }
        return action


    @api.depends('sale_order_id')
    def _compute_sale_order_count(self):
        """Return 1 when a sale order is linked, else 0."""
        for rec in self:
            rec.sale_order_count = 1 if rec.sale_order_id else 0

    def action_open_sale_order(self):
        """Navigate to the linked sales order form."""
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
        """Print the manifest PDF report."""
        self.ensure_one()

        if self.state not in ["done", "scheduled"]:
            raise UserError(_("Only Authorised or Scheduled manifests can be printed."))

        return self.env.ref(
            "waste_management_zakheni.action_manifest_report_pdf"
        ).report_action(self)
