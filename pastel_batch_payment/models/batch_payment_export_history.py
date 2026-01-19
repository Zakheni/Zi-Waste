from odoo import models, fields


class BatchPaymentExportHistory(models.Model):
    _name = "batch.payment.export.history"
    _description = "Batch Payment Export History"
    _order = "export_date desc"

    batch_id = fields.Many2one(
        "batch.payment",
        required=True,
        ondelete="cascade",
    )

    export_date = fields.Datetime(
        string="Export Date",
        default=fields.Datetime.now,
        required=True,
    )

    user_id = fields.Many2one(
        "res.users",
        string="Exported By",
        default=lambda self: self.env.user,
        required=True,
    )

    state = fields.Selection(
        [
            ("success", "Success"),
            ("failed", "Failed"),
        ],
        required=True,
    )

    sage_reference = fields.Char(
        string="Sage Reference"
    )

    request_payload = fields.Text(
        string="Request Payload (JSON)"
    )

    response_payload = fields.Text(
        string="Response / Error"
    )
