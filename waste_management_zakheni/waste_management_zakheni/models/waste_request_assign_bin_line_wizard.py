"""Wizard line model for assign-bin workflow (legacy/alternate)."""
from odoo import models, fields, api


class WasteAssignBinWizardLine(models.TransientModel):
    """Pickup-point line in the assign-bin wizard."""
    _name = 'waste.request.assign.bin.line.wizard'
    _description = 'Assign Bins Wizard Line'

    wizard_id = fields.Many2one(
        'waste.request.assign.bin.wizard',
        string="Wizard",
        required=True,
        ondelete='cascade',
    )

    # service code from parent wizard (used for attrs + domains)
    svc_code = fields.Char(
        related='wizard_id.svc_code',
        store=False,
        string="Service Code",
    )

    pickup_point_id = fields.Many2one(
        'pickup.point',
        string="Pickup / Dropoff Point",
        help="Pickup point (also works as dropoff point).",
    )

    # ------------------------------------------------------------
    # 1) Placement / Removal / Waste Collection (uses container_ids)
    # ------------------------------------------------------------
    container_ids = fields.Many2many(
        'waste.container',
        'waste_assign_bin_wizard_line_cont_rel',
        'line_id',
        'container_id',
        string="Containers",
        help="Bins for Placement / Removal / Waste Collection & Disposal.",
    )

    # ------------------------------------------------------------
    # 2) Shunting of Bins (uses shunt_container_ids)
    # ------------------------------------------------------------
    shunt_container_ids = fields.Many2many(
        'waste.container',
        'waste_assign_bin_wizard_line_shunt_rel',
        'line_id',
        'container_id',
        string="Bins to Shunt",
        help="Bins selected for shunting.",
    )

    # ------------------------------------------------------------
    # 3) Swapping of Bins (lifted + dropped)
    # ------------------------------------------------------------
    lifted_container_ids = fields.Many2many(
        'waste.container',
        'waste_assign_bin_wizard_line_lifted_rel',
        'line_id',
        'container_id',
        string="Lifted Bins",
        help="Bins being lifted (removed) from pickup point.",
    )

    dropped_container_ids = fields.Many2many(
        'waste.container',
        'waste_assign_bin_wizard_line_dropped_rel',
        'line_id',
        'container_id',
        string="Dropped Bins",
        help="New bins being dropped (must be free/intact).",
    )

    # ------------------------------------------------------------
    # Dynamic domains based on service type + pickup point + customer + bin_type
    # ------------------------------------------------------------
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

            # ---------- Placement of Bins ----------
            if svc == 'placement of bins':
                domains['container_ids'] = base_dom + [
                    ('pickup_point_id', '=', False),
                    ('customer_id', '=', False),
                    ('status', 'in', ['intact', 'un_use']),
                ]

            # ---------- Removal of Bins ----------
            elif svc == 'removal of bins':
                domains['container_ids'] = base_dom + [
                    ('pickup_point_id', '=', line.pickup_point_id.id if line.pickup_point_id else False),
                    ('customer_id', '=', customer.id if customer else False),
                    ('status', 'in', ['intact', 'in_use', 'broken']),
                ]

            # ---------- Waste Collection & Disposal ----------
            elif svc == 'waste collection & disposal':
                domains['container_ids'] = base_dom + [
                    ('pickup_point_id', '=', line.pickup_point_id.id if line.pickup_point_id else False),
                    ('customer_id', '=', customer.id if customer else False),
                    ('status', 'in', ['in_use', 'broken', 'un_use']),
                ]

            # ---------- Shunting of Bins ----------
            elif svc == 'shunting of bins':
                domains['shunt_container_ids'] = base_dom + [
                    ('pickup_point_id', '=', line.pickup_point_id.id if line.pickup_point_id else False),
                    ('customer_id', '=', customer.id if customer else False),
                ]

            # ---------- Swapping of Bins ----------
            elif svc == 'swapping of bins':
                domains['lifted_container_ids'] = base_dom + [
                    ('pickup_point_id', '=', line.pickup_point_id.id if line.pickup_point_id else False),
                    ('customer_id', '=', customer.id if customer else False),
                    ('status', 'in', ['broken', 'in_use', 'un_use']),
                ]
                domains['dropped_container_ids'] = base_dom + [
                    ('pickup_point_id', '=', False),
                    ('customer_id', '=', False),
                    ('status', 'in', ['intact']),
                ]

            return {'domain': domains}

