from odoo import models

class AccountMove(models.Model):
    _inherit = "account.move"

    def action_register_payment_batch(self):
        self.ensure_one()
        action = self.action_register_payment()
        ctx = dict(action.get("context", {}) or {})
        ctx.update({"batch_skip_reconcile": True})
        action["context"] = ctx
        return action


# # -*- coding: utf-8 -*-
# from odoo import models
#
#
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     def action_register_payment_batch(self):
#         self.ensure_one()
#         action = self.action_register_payment()
#         ctx = dict(action.get("context", {}) or {})
#         ctx.update({"batch_skip_reconcile": True})
#         action["context"] = ctx
#         return action


# from odoo import models
#
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     def action_register_payment_batch(self):
#         self.ensure_one()
#         action = self.action_register_payment()
#         ctx = dict(action.get("context", {}) or {})
#         ctx.update({"batch_skip_reconcile": True})
#         action["context"] = ctx
#         return action
