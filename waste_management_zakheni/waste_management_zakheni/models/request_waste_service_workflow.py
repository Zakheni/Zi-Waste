"""Workflow state transitions and container authorisation for waste manifests."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WasteServiceRequestWorkflow(models.Model):
    """Mixin: manifest lifecycle actions and container side-effects on authorise."""

    _inherit = 'waste.service.request'

    # ---------------------------------------------------------
    # Status actions
    # ---------------------------------------------------------

    def action_draft(self):
        """Reset manifest state back to draft."""
        self.write({'state': 'draft'})

    def action_generated(self):
        """Confirm manifest and mark linked containers as in use."""
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
        """
        Move manifest to scheduled, create worksheet, and notify the assigned driver or provider.

        Workflow: generated → scheduled. The selected driver remains linked via driver_id
        so driver record rules and worksheets show the assignment.
        """
        Worksheet = self.env['waste.worksheet'].sudo()

        for rec in self:
            if rec.state != 'generated':
                raise UserError(_("Only generated manifests can be scheduled."))

            if not rec.planned_date:
                raise UserError(_("Please enter the planned date before scheduling."))

            if rec.is_service_provider:
                if not rec.provider_id and not rec.provider_name:
                    raise UserError(_("Please select a service provider before scheduling."))
            else:
                if not rec.vehicle_id:
                    raise UserError(_("Please select a vehicle before scheduling."))
                if not rec.driver_id:
                    raise UserError(_("Please select a driver before scheduling."))

            rec.state = 'scheduled'

            existing_ws = Worksheet.search([
                ('service_request_id', '=', rec.id),
            ], limit=1)

            if not existing_ws:
                existing_ws = Worksheet.with_context(skip_transport_sync=True).create({
                    'service_request_id': rec.id,
                    'company_id': rec.company_id.id,
                })

            if rec.driver_id:
                rec.message_subscribe(partner_ids=[rec.driver_id.id])
                existing_ws.message_subscribe(partner_ids=[rec.driver_id.id])
                rec.message_post(
                    body=_("Manifest scheduled and assigned to driver %s.") % rec.driver_id.display_name,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )

            if rec.is_service_provider:
                template = rec.env.ref(
                    "waste_management_zakheni.mail_tmpl_service_request_service_provide_invitation",
                    raise_if_not_found=False,
                )
                if template and rec.provider_email:
                    template.sudo().send_mail(rec.id, force_send=True)
            else:
                template = rec.env.ref(
                    "waste_management_zakheni.mail_tmpl_service_request_driver_invitation",
                    raise_if_not_found=False,
                )
                if template and rec.driver_work_email:
                    template.sudo().send_mail(rec.id, force_send=True)

        return True

    def action_authorise(self, finance_email=None):
        """
        Final authorisation step: mark manifest done and notify finance.

        Called from authorize.wizard after container side-effects in action_mark_done.

        Args:
            finance_email (str, optional): Override recipient for the finance email.

        Returns:
            bool: True when processed.
        """
        for rec in self.sudo():
            rec.state = 'done'
            template = rec.env.ref(
                'waste_management_zakheni.mail_tmpl_service_request_authorize',
                raise_if_not_found=False,
            )
            email_to = finance_email or rec.finance_email
            if template and email_to:
                template.sudo().send_mail(
                    rec.id,
                    force_send=True,
                    raise_exception=True,
                    email_values={'email_to': email_to},
                )
        return True

    def action_mark_done(self):
        """Apply container side-effects and open the authorisation wizard."""
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
                },
            }

