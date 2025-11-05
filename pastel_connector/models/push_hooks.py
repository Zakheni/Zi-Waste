# models/push_hooks.py
from odoo import models, api

def _push_enabled(env):
    s = env["pastel.connector.setting"].sudo().search([], limit=1)
    return bool(s and s.enable_push_to_sage)

# ---------------- Customers ----------------
class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if _push_enabled(self.env):
            for p in recs.filtered(lambda r: r.customer_rank > 0):
                self.env["pastel.sync"].sudo().push_customer(p)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if _push_enabled(self.env):
            for p in self.filtered(lambda r: r.customer_rank > 0):
                self.env["pastel.sync"].sudo().push_customer(p)
        return res

    def unlink(self):
        if _push_enabled(self.env):
            for p in self.filtered(lambda r: r.customer_rank > 0):
                self.env["pastel.sync"].sudo().delete_customer(p)
        return super().unlink()

# ---------------- Products ----------------
class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if _push_enabled(self.env):
            for t in recs:
                self.env["pastel.sync"].sudo().push_product(t)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if _push_enabled(self.env):
            for t in self:
                self.env["pastel.sync"].sudo().push_product(t)
        return res

    def unlink(self):
        if _push_enabled(self.env):
            for t in self:
                self.env["pastel.sync"].sudo().delete_product(t)
        return super().unlink()

# ---------------- Invoices ----------------
class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        res = super().action_post()
        if _push_enabled(self.env):
            for m in self.filtered(lambda x: x.move_type == "out_invoice" and x.state == "posted"):
                self.env["pastel.sync"].sudo().push_invoice(m)
        return res

    def write(self, vals):
        """If a posted customer invoice is edited (e.g., lines or date), push again."""
        res = super().write(vals)
        if _push_enabled(self.env):
            for m in self.filtered(lambda x: x.move_type == "out_invoice" and x.state == "posted"):
                self.env["pastel.sync"].sudo().push_invoice(m)
        return res
