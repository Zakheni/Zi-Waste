# models/waste_schedule.py
from odoo import models, fields, api


class WasteCapture(models.Model):
    _name = "waste.capture"
    _description = "Waste Captured"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "return_date"

    service_request_id = fields.Many2one(
        "waste.service.request",
        string="Service Request",
        ondelete="set null"
    )

    return_date = fields.Datetime(string='Return Date')
    capacity_tons = fields.Float(string='Captured Tons')
    unit_of_measure = fields.Many2one('uom.uom', string='Units of Measure')
    # comment = fields.Text(string='Comment')

    planned_date = fields.Datetime(string='Planned Date', related='service_request_id.planned_date', store=True)

    partner_id = fields.Many2one('res.partner', string="Customer", related='service_request_id.partner_id')
    pickup_point_id = fields.Many2one('pickup.point', string="Drop-off/Pickup Point",
                                      related='service_request_id.pickup_point_id')

    service_requested = fields.Selection([
        ('placement_of_bins', 'Placement of Bins'),
        ('shunting_of_bins', 'Shunting of Bins'),
        ('removal_of_bins', 'Removal of Bins'),
        ('waste_collection_&_disposal', 'Waste Collection & Disposal'),
        ('swapping_of_bins', 'Swapping of Bins'),
        ('none', 'None'),
    ], string="Service Requested", related='service_request_id.service_requested')

    waste_type = fields.Selection([
        ('hazardous', 'Hazardous'),
        ('general_non-compactable', 'General Non-Compactable'),
        ('general_compactable', 'General Compactable'),
        ('none', 'None')
    ], string="Waste Type", related='service_request_id.waste_type')

    waste_details = fields.Selection([
        ('recyclable', 'Recyclable'),
        ('non-recyclable', 'Non-Recyclable'),
        ('ammonium_nitrate', 'Ammonium Nitrate'),
        ('used_coal', 'Used Coal'),
        ('computer_waste', 'Computer Waste'),
        ('general_waste', 'General Waste'),
        ('chemical', 'Chemical'),
        ('sulphur', 'Sulphur'),
        ('rubber', 'Rubber'),
        ('copper_sulphide', 'Copper Sulphide'),
        ('hazardous', 'Hazardous'),
        ('none', 'None'),

    ], string="Waste Details", related='service_request_id.waste_details')

    bin_type = fields.Selection([
        ('6m³', '6m³'),
        ('9m³', '9m³'),
        ('11m³', '11m³'),
        ('18m³', '18m³'),
        ('28m³', '28m³'),
        ('none', 'None'),
    ], string="Bin Type", related='service_request_id.bin_type')

    tank_volume = fields.Selection([
        ('7000_liters', '7000 Liters'),
        ('9000_liters', '9000 Liters'),
        ('11000_liters', '11000 Liters'),
        ('12000_liters', '12000 Liters'),
        ('15000_liters', '15000 Liters'),
        ('none', 'None'),
    ], string="Tank Volume", related='service_request_id.tank_volume')
    container_type = fields.Selection([
        ('bin', 'Bin'),
        ('tank', 'Tank'),
        ('none', 'None')
    ], String="Container Type", default='', related='service_request_id.container_type'
    )
    inUse = fields.Boolean(string='InUse', related='service_request_id.inUse', defauld=True, )
    tank_ids = fields.Many2many('waste.container', 'waste_service_request_tanks_rel', string="Tanks",
                                related='service_request_id.tank_ids')
    # Shunt
    shunt_from_id = fields.Many2one('pickup.point', string="From Location", domain="[('partner_id', '=', partner_id)]",
                                    related='service_request_id.shunt_from_id')
    shunt_to_id = fields.Many2one('pickup.point', string="To Location", domain="[('partner_id', '=', partner_id)]",
                                  related='service_request_id.shunt_to_id')

    lifted_bin_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_lifted_rel',  # Different relation table
        'request_id',
        'container_id',
        string="Lifted Bins", related='service_request_id.lifted_bin_ids'
    )
    dropped_bin_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_dropped_rel',  # Different relation table
        'request_id',
        'container_id',
        string="New Bins (Dropped)",
        related='service_request_id.dropped_bin_ids'
    )
    # Placement & Collection
    dropoff_container_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_containers_rel',
        string="Containers",
        related='service_request_id.dropoff_container_ids'
    )
    # Shunt
    shunt_container_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_shunt_rel',
        string="Containers",
        related='service_request_id.shunt_container_ids'
    )
    # Shunt
    shunted_bin_ids = fields.Many2many(
        'waste.container',
        'waste_service_request_shunted_rel',  # Different relation table
        'request_id',
        'container_id',
        string="Bins to Shunt",
        related='service_request_id.shunted_bin_ids'
    )

    state = fields.Selection([
        ("draft", "Draft"),
        ("done", "Captured"),
    ], string="Status", default="draft", required=True)

    # ----------------------
    # Button Actions
    # ----------------------
    def action_set_to_draft(self):
        self.state = "draft"

    def action_set_to_captured(self):
        for rec in self:
            rec.state = "done"
            # if rec.service_request_id:
            #     rec.service_request_id.state = "done"

    # driver_signature = fields.Binary(string="Driver Signature", stotre=True)
    # html_signature = fields.Html(string="Signature Preview", compute="_compute_html_signature", store=True)
    # signature_log_ids = fields.One2many('driver.signature', 'user_id', string="Signature History", store=True)

    def action_signature(self):
        self.ensure_one()
        return {
            'name': 'Driver Signature',
            'type': 'ir.actions.act_window',
            'res_model': 'driver.signature',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    # @api.depends("driver_signature")
    # def _compute_html_signature(self):
    #     for rec in self:
    #         if rec.driver_signature:
    #             rec.html_signature = f"""
    #                     <div style="border:1px solid #ccc; padding:5px; display:inline-block;">
    #                         <img src="data:image/png;base64,{rec.driver_signature.decode()}" style="height:80px;"/>
    #                     </div>
    #                 """
    #         else:
    #             rec.html_signature = "<p>No signature yet.</p>"



    # def action_signature(self):
    #     self.ensure_one()
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Enter Signature',
    #         'res_model': 'driver.signature',
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'context': {
    #             'default_user_id': self.id,
    #         },
    #     }
    #
    # driver_signature = fields.Binary(string="Driver Signature")
    # driver_signature_ids = fields.One2many('driver.signature', 'user_id', string="Signature History")
    # html_signature = fields.Html(string="Signature Preview", compute="_compute_html_signature", sanitize=False)
    #
    # @api.depends("driver_signature_ids")
    # def _compute_html_signature(self):
    #     for rec in self:
    #         if rec.driver_signature:
    #             rec.html_signature = f"""
    #                     <div>
    #                         <img src="data:image/png;base64,{rec.driver_signature.decode()}" style="height:80px;" />
    #                     </div>
    #                 """
    #         else:
    #             rec.html_signature = "<p>No signature yet.</p>"

    driver_signature = fields.Binary(string="Driver Signature")
    driver_signature_ids = fields.One2many('driver.signature', 'user_id', string="Driver Signature")

    # HTML field to display the summary table
    html_table = fields.Html(string="Audit Trail", compute="_compute_html_table", store=True)
    #
    # --- Compute Method for HTML Table ---
    @api.depends('driver_signature_ids')
    def _compute_html_table(self):
        """
        Computes the HTML table representation of the audit trail.
        Combines information from HR Report Lines and Verification Comments.
        """
        for rec in self:
            rows = ""
            all_lines = []

            for line in rec.driver_signature_ids:
                all_lines.append({
                    'signature': line.driver_signature.decode() if line.driver_signature else None
                })

            if all_lines:
                for line_data in all_lines:
                    signature_img = 'N/A'
                    if line_data['signature']:
                        signature_img = (
                            f'<img src="data:image/png;base64,{line_data["signature"]}" '
                            f'style="height:40px;" />'
                        )

                    # Build HTML row
                    rows += (f"<tr>"
                             f"<td>{signature_img}</td>"
                             f"</tr>"
                             )

                rec.html_table = f"""
                       <div class="">
                           <table id="auditTrailTable" class="table table-borderless table-sm">
                               <thead>
                                   <tr>
                                       <th>Signature</th>
                                   </tr>
                               </thead>
                               <tbody>{rows}</tbody>
                           </table>
                       </div>
                   """
            else:
                rec.html_table = "<p>No audit trail entries yet.</p>"
