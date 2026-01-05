# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BatchPaymentAddWizard(models.TransientModel):
    _name = "batch.payment.add.wizard"
    _description = "Select Posted Payments to Add"

    batch_id = fields.Many2one("batch.payment", required=True)

    payment_ids = fields.Many2many(
        "account.payment",
        string="Posted Payments",
        domain=[('state', '=', 'posted')],
        help="Select one or more posted payments to add to the batch."
    )

    def action_add(self):
        self.ensure_one()
        batch = self.batch_id
        if not self.payment_ids:
            raise UserError(_("Please select at least one payment."))

        existing = set(batch.line_ids.mapped("payment_id").ids)
        to_create = []

        for pay in self.payment_ids:
            if pay.id in existing:
                continue

            to_create.append((0, 0, {
                "payment_id": pay.id,
                "communication": pay.ref or pay.name or batch.name or "",
                "move_id": pay.batch_invoice_id.id if getattr(pay, "batch_invoice_id", False) else False,
            }))

        if not to_create:
            raise UserError(_("All selected payments are already in this batch."))

        batch.write({"line_ids": to_create})
        return {"type": "ir.actions.act_window_close"}


# from odoo import api, fields, models, _
# from odoo.exceptions import UserError
#
# class BatchPaymentAddWizard(models.TransientModel):
#     _name = "batch.payment.add.wizard"
#     _description = "Select Posted Payments to Add"
#
#     batch_id = fields.Many2one("batch.payment", required=True)
#     # Let the user select multiple posted payments; domain is injected from context
#     payment_ids = fields.Many2many(
#         "account.payment",
#         string="Posted Payments",
#         domain=[('state', '=', 'posted')],
#         help="Select one or more posted payments to add to the batch."
#     )
#
#     def action_add(self):
#         self.ensure_one()
#         batch = self.batch_id
#         if not self.payment_ids:
#             raise UserError(_("Please select at least one payment."))
#
#         # # Create lines for selected payments (skip duplicates)
#         # existing = set(batch.line_ids.mapped("payment_id").ids)
#         # to_create = []
#         # for pay in self.payment_ids:
#         #     if pay.id in existing:
#         #         continue
#         #     to_create.append((0, 0, {
#         #         "payment_id": pay.id,
#         #         "communication": pay.ref or pay.name or batch.name or "",
#         #     }))
#
#         existing = set(batch.line_ids.mapped("payment_id").ids)
#         to_create = []
#         for pay in self.payment_ids:
#             if pay.id in existing:
#                 continue
#             to_create.append((0, 0, {
#                 "payment_id": pay.id,
#                 "communication": pay.ref or pay.name or batch.name or "",
#                 "move_id": pay.batch_invoice_id.id if getattr(pay, "batch_invoice_id", False) else False,
#             }))
#
#         if not to_create:
#             raise UserError(_("All selected payments are already in this batch."))
#
#         batch.write({"line_ids": to_create})
#         return {"type": "ir.actions.act_window_close"}
#
#
#
#
