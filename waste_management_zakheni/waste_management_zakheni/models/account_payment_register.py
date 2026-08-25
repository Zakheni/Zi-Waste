"""Payment register wizard extensions for waste billing."""

# import logging
#
# from odoo import models
#
# _logger = logging.getLogger(__name__)
#
# class AccountPaymentRegister(models.TransientModel):
#     """Customise payment registration behaviour for waste invoices."""
#     _inherit = "account.payment.register"
#
#     def action_create_payments(self):
#         # 1️⃣ Capture invoices FIRST
#         invoices = self.env['account.move'].browse(
#             self._context.get("active_ids", [])
#         ).filtered(lambda m: m.move_type == "out_invoice" and m.exists())
#
#         # 2️⃣ Create payments
#         res = super().action_create_payments()
#
#         _logger.info("Sending invoice %s exists=%s", invoices.id, invoices.exists())
#
#         # 3️⃣ Send emails AFTER payment
#         template = self.env.ref(
#             "account.email_template_edi_invoice",
#             raise_if_not_found=False
#         )
#
#         for invoice in invoices:
#             if (
#                 invoice.exists()
#                 and invoice.state == "posted"
#                 and invoice.partner_id.email
#                 and template
#             ):
#                 template.with_context(
#                     force_email=True
#                 ).send_mail(
#                     invoice.id,
#                     force_send=True,
#                 )
#
#         return res
