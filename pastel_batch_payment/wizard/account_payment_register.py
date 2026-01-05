# -*- coding: utf-8 -*-
from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _reconcile_payments(self, to_process, edit_mode=False, **kwargs):
        # Skip reconciliation only in batch mode
        if self.env.context.get("batch_skip_reconcile"):
            return
        # Safe super call (handles signature differences)
        try:
            return super()._reconcile_payments(to_process, edit_mode=edit_mode, **kwargs)
        except TypeError:
            try:
                return super()._reconcile_payments(to_process, edit_mode=edit_mode)
            except TypeError:
                return super()._reconcile_payments(to_process)

    def action_create_payments(self):
        """
        Odoo 17 entry point when user clicks Register Payment.
        Tag created payments with invoice so batch can reconcile later.
        """
        res = super().action_create_payments()

        if not self.env.context.get("batch_skip_reconcile"):
            return res

        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids") or []
        if active_model != "account.move" or not active_ids:
            return res

        invoice = self.env["account.move"].browse(active_ids[0]).exists()
        if not invoice:
            return res

        payments = self.payment_id

        # Fallback: sometimes action returns a res_id to a payment
        if not payments and isinstance(res, dict):
            if res.get("res_model") == "account.payment" and res.get("res_id"):
                payments = self.env["account.payment"].browse(res["res_id"]).exists()

        if payments:
            payments.write({"batch_invoice_id": invoice.id})

        return res


# # -*- coding: utf-8 -*-
# from odoo import models
#
#
# class AccountPaymentRegister(models.TransientModel):
#     _inherit = "account.payment.register"
#
#     def _reconcile_payments(self, to_process, edit_mode=False, **kwargs):
#         """
#         Odoo 17 calls this with keyword edit_mode=...
#         Some builds / older variants may call it without that kw.
#         We support both safely and skip reconciliation only in batch mode.
#         """
#         if self.env.context.get("batch_skip_reconcile"):
#             return
#
#         # Call super safely across signature variants
#         try:
#             return super()._reconcile_payments(to_process, edit_mode=edit_mode, **kwargs)
#         except TypeError:
#             # Fallback: some variants don't accept edit_mode or extra kwargs
#             try:
#                 return super()._reconcile_payments(to_process, edit_mode=edit_mode)
#             except TypeError:
#                 return super()._reconcile_payments(to_process)
#
#     def action_create_payments(self):
#         """
#         Entry point when user clicks Register Payment.
#         After super() creates & posts payment(s), tag them with the source invoice
#         when in batch mode so BatchPayment can reconcile later.
#         """
#         res = super().action_create_payments()
#
#         if not self.env.context.get("batch_skip_reconcile"):
#             return res
#
#         active_model = self.env.context.get("active_model")
#         active_ids = self.env.context.get("active_ids") or []
#         if active_model != "account.move" or not active_ids:
#             return res
#
#         invoice = self.env["account.move"].browse(active_ids[0]).exists()
#         if not invoice:
#             return res
#
#         # In Odoo 17 this is usually set by the wizard after creation
#         payments = self.payment_id
#
#         # Fallback: sometimes res opens a payment record directly
#         if not payments and isinstance(res, dict):
#             if res.get("res_model") == "account.payment" and res.get("res_id"):
#                 payments = self.env["account.payment"].browse(res["res_id"]).exists()
#
#         if payments:
#             # Write invoice link onto created payment(s)
#             payments.write({"batch_invoice_id": invoice.id})
#
#         return res
#
#
# # # -*- coding: utf-8 -*-
# # from odoo import models
# #
# #
# # class AccountPaymentRegister(models.TransientModel):
# #     _inherit = "account.payment.register"
# #
# #     def _reconcile_payments(self, to_process, edit_mode=False, **kwargs):
# #         # Skip reconciliation only in batch mode
# #         if self.env.context.get("batch_skip_reconcile"):
# #             return
# #         return super()._reconcile_payments(to_process, edit_mode=edit_mode, **kwargs)
# #
# #     def action_create_payments(self):
# #         """
# #         Odoo 17 entry point when user clicks Register Payment.
# #         We hook here to guarantee we can tag created payments with the source invoice.
# #         """
# #         res = super().action_create_payments()
# #
# #         if self.env.context.get("batch_skip_reconcile"):
# #             active_model = self.env.context.get("active_model")
# #             active_ids = self.env.context.get("active_ids") or []
# #             if active_model == "account.move" and active_ids:
# #                 invoice = self.env["account.move"].browse(active_ids[0]).exists()
# #                 if invoice and self.payment_id:
# #                     self.payment_id.write({"batch_invoice_id": invoice.id})
# #
# #         return res
# #
# #
# # # # -*- coding: utf-8 -*-
# # # from odoo import models
# # #
# # # class AccountPaymentRegister(models.TransientModel):
# # #     _inherit = "account.payment.register"
# # #
# # #     def _reconcile_payments(self, to_process, edit_mode=False, **kwargs):
# # #         # Skip reconciliation only in batch mode
# # #         if self.env.context.get("batch_skip_reconcile"):
# # #             return
# # #         return super()._reconcile_payments(to_process, edit_mode=edit_mode, **kwargs)
# # #
# # #     def action_create_payments(self):
# # #         """
# # #         Odoo 17 entry point when user clicks 'Create Payment' / 'Register Payment'.
# # #         We hook here to guarantee we can tag the created payments with the source invoice.
# # #         """
# # #         res = super().action_create_payments()
# # #
# # #         if self.env.context.get("batch_skip_reconcile"):
# # #             active_model = self.env.context.get("active_model")
# # #             active_ids = self.env.context.get("active_ids") or []
# # #             if active_model == "account.move" and active_ids:
# # #                 invoice = self.env["account.move"].browse(active_ids[0]).exists()
# # #                 if invoice:
# # #                     # Payments created by this wizard are on self.payment_id(s)
# # #                     payments = self.payment_id
# # #                     if payments:
# # #                         payments.write({"batch_invoice_id": invoice.id})
# # #
# # #         return res
# # #
# # #
# # # # # -*- coding: utf-8 -*-
# # # # from odoo import models
# # # #
# # # # class AccountPaymentRegister(models.TransientModel):
# # # #     _inherit = "account.payment.register"
# # # #
# # # #     def _reconcile_payments(self, to_process, edit_mode=False, **kwargs):
# # # #         # Skip reconciliation only in batch mode
# # # #         if self.env.context.get("batch_skip_reconcile"):
# # # #             return
# # # #         return super()._reconcile_payments(to_process, edit_mode=edit_mode, **kwargs)
# # # #
# # # #     def _create_payments(self):
# # # #         payments = super()._create_payments()
# # # #
# # # #         # If this wizard was launched from an invoice in batch mode,
# # # #         # store the invoice on the created payment(s)
# # # #         if self.env.context.get("batch_skip_reconcile"):
# # # #             active_model = self.env.context.get("active_model")
# # # #             active_ids = self.env.context.get("active_ids") or []
# # # #             if active_model == "account.move" and active_ids:
# # # #                 # usually 1 invoice -> 1 payment
# # # #                 invoice = self.env["account.move"].browse(active_ids[0]).exists()
# # # #                 if invoice:
# # # #                     payments.write({"batch_invoice_id": invoice.id})
# # # #
# # # #         return payments
# # # #
# # # #
# # # # # # -*- coding: utf-8 -*-
# # # # # from odoo import models
# # # # #
# # # # # class AccountPaymentRegister(models.TransientModel):
# # # # #     _inherit = "account.payment.register"
# # # # #
# # # # #     def _reconcile_payments(self, to_process, edit_mode=False, **kwargs):
# # # # #         """
# # # # #         Odoo 17 signature:
# # # # #             _reconcile_payments(to_process, edit_mode=False)
# # # # #
# # # # #         We skip reconciliation ONLY when the wizard is launched in batch mode
# # # # #         (context flag: batch_skip_reconcile=True).
# # # # #         """
# # # # #         if self.env.context.get("batch_skip_reconcile"):
# # # # #             # Do nothing: payment will be created + posted, but invoice remains open (Posted).
# # # # #             return
# # # # #
# # # # #         return super()._reconcile_payments(to_process, edit_mode=edit_mode, **kwargs)
