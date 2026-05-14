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



