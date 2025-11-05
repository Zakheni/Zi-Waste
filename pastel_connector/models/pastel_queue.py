import json
import requests
from odoo import models, fields, api, _

JSON = "application/json"


# ---------------------------------------------------------------------
# History log
# ---------------------------------------------------------------------
class PastelSyncLog(models.Model):
    _name = "pastel.sync.log"
    _description = "Pastel Sync History"
    _order = "create_date desc"

    kind = fields.Selection([
        ("customer", "Customer"),
        ("supplier", "Supplier"),
        ("product", "Product"),
        ("invoice", "Invoice"),
    ], required=True)

    imported = fields.Integer(default=0)
    #exported = fields.Integer(default=0)
    updated = fields.Integer(default=0)
    deleted = fields.Integer(default=0)
    notes = fields.Char()
    create_date = fields.Datetime(readonly=True)


# ---------------------------------------------------------------------
# Queue (push Odoo → Sage via the bridge)
# ---------------------------------------------------------------------
class PastelSyncQueue(models.Model):
    _name = "pastel.sync.queue"
    _description = "Pastel Sync Queue (push to Sage)"
    _order = "id asc"

    model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    operation = fields.Selection([("create", "Create"), ("write", "Write"), ("unlink", "Unlink")], required=True)
    payload = fields.Text()  # JSON
    # NEW: who is this partner for?
    role = fields.Selection([("customer", "Customer"), ("supplier", "Supplier"), ("both", "Both")])
    state = fields.Selection([("pending", "Pending"), ("done", "Done"), ("error", "Error")], default="pending")
    error = fields.Text()

    def _push_enabled(self):
        S = self.env["pastel.connector.setting"].sudo().search([], limit=1)
        return bool(S and S.enable_push_to_sage)

    def process_queue(self, limit=50):
        base, key = self.env["pastel.sync"]._conf()
        processed = 0
        for rec in self.search([("state", "=", "pending")], limit=limit):
            try:
                if not self._push_enabled():
                    rec.write({"state": "done", "error": "Skipped: push disabled"})
                    processed += 1
                    continue

                data = json.loads(rec.payload or "{}")

                # Decide endpoint(s)
                paths = []
                if rec.model == "res.partner":
                    role = rec.role or data.get("role")
                    if role == "customer":
                        paths = ["/customers"]
                    elif role == "supplier":
                        paths = ["/suppliers"]
                    else:
                        # default to pushing to both if unclear
                        paths = ["/customers", "/suppliers"]
                elif rec.model == "product.template":
                    paths = ["/products"]
                elif rec.model == "account.move":
                    paths = ["/invoices"]
                else:
                    rec.write({"state": "error", "error": "Unsupported model"})
                    continue

                # HTTP method + URL
                def one_call(path):
                    if rec.operation == "create":
                        method, url = "POST", path
                    elif rec.operation == "write":
                        ext = (data.get("external_key")
                               or data.get("code")
                               or data.get("doc_no")
                               or rec.res_id)
                        method, url = "PUT", f"{path}/{ext}"
                    else:  # unlink
                        ext = (data.get("external_key")
                               or data.get("code")
                               or data.get("doc_no")
                               or rec.res_id)
                        method, url = "DELETE", f"{path}/{ext}"
                    self.env["pastel.sync"]._req(method, url, key, base, json=data)

                # Perform one or many (for partners)
                for p in paths:
                    one_call(p)

                rec.write({"state": "done", "error": False})
                processed += 1

            except requests.HTTPError as e:
                # Friendly skip for 405 (bridge route not implemented)
                if getattr(e.response, "status_code", None) == 405:
                    rec.write({"state": "done", "error": "Skipped: bridge method not implemented (405)"})
                    processed += 1
                else:
                    rec.write({"state": "error", "error": str(e)})
            except Exception as e:
                rec.write({"state": "error", "error": str(e)})
        return processed


# ---------------------------------------------------------------------
# Partner hooks (Customer/Supplier)
# ---------------------------------------------------------------------
class ResPartner(models.Model):
    _inherit = "res.partner"

    # Decide role once per record
    def _pastel_role(self):
        self.ensure_one()
        cust = bool(self.customer_rank)
        supp = bool(self.supplier_rank)
        if cust and supp:
            return "both"
        if supp:
            return "supplier"
        return "customer"

    def _to_pastel_payload(self):
        self.ensure_one()
        # One payload works for both endpoints; bridge decides how to store
        return {
            "code": self.x_pastel_code or self.ref or str(self.id),
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "credit_limit": self.x_pastel_credit_limit,
            "tax_code": self.x_pastel_tax_code,
            "currency_code": self.x_pastel_currency_code,
            "category": self.x_pastel_category,
            "open_item": self.x_pastel_open_item,
            "role": self._pastel_role(),  # include role in JSON too
        }

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        if self.env["pastel.sync.queue"]._push_enabled():
            self.env["pastel.sync.queue"].sudo().create({
                "model": "res.partner",
                "res_id": rec.id,
                "operation": "create",
                "role": rec._pastel_role(),
                "payload": json.dumps(rec._to_pastel_payload()),
            })
        return rec

    def write(self, vals):
        res = super().write(vals)
        if self.env["pastel.sync.queue"]._push_enabled():
            for rec in self:
                self.env["pastel.sync.queue"].sudo().create({
                    "model": "res.partner",
                    "res_id": rec.id,
                    "operation": "write",
                    "role": rec._pastel_role(),
                    "payload": json.dumps(
                        rec._to_pastel_payload() | {"external_key": rec.x_pastel_code or rec.ref or str(rec.id)}
                    ),
                })
        return res

    def unlink(self):
        if self.env["pastel.sync.queue"]._push_enabled():
            for rec in self:
                self.env["pastel.sync.queue"].sudo().create({
                    "model": "res.partner",
                    "res_id": rec.id,
                    "operation": "unlink",
                    "role": rec._pastel_role(),
                    "payload": json.dumps({"code": rec.x_pastel_code or rec.ref or str(rec.id),
                                           "role": rec._pastel_role()}),
                })
        return super().unlink()


# ---------------------------------------------------------------------
# Product hooks
# ---------------------------------------------------------------------
class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _to_pastel_payload(self):
        self.ensure_one()
        return {
            "code": self.x_pastel_item_code or self.default_code or str(self.id),
            "name": self.name,
            "tax_code": self.x_pastel_tax_code,
            "price_regime": self.x_pastel_price_regime,
        }

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        if self.env["pastel.sync.queue"]._push_enabled():
            self.env["pastel.sync.queue"].sudo().create({
                "model": "product.template",
                "res_id": rec.id,
                "operation": "create",
                "payload": json.dumps(rec._to_pastel_payload()),
            })
        return rec

    def write(self, vals):
        res = super().write(vals)
        if self.env["pastel.sync.queue"]._push_enabled():
            for rec in self:
                self.env["pastel.sync.queue"].sudo().create({
                    "model": "product.template",
                    "res_id": rec.id,
                    "operation": "write",
                    "payload": json.dumps(
                        rec._to_pastel_payload() | {"external_key": rec.x_pastel_item_code or rec.default_code or str(rec.id)}
                    ),
                })
        return res

    def unlink(self):
        if self.env["pastel.sync.queue"]._push_enabled():
            for rec in self:
                self.env["pastel.sync.queue"].sudo().create({
                    "model": "product.template",
                    "res_id": rec.id,
                    "operation": "unlink",
                    "payload": json.dumps({"code": rec.x_pastel_item_code or rec.default_code or str(rec.id)}),
                })
        return super().unlink()


# ---------------------------------------------------------------------
# Invoice hooks (Customer invoices only)
# ---------------------------------------------------------------------
class AccountMove(models.Model):
    _inherit = "account.move"

    def _to_pastel_payload(self):
        self.ensure_one()
        data = {
            "doc_no": self.x_pastel_doc_no or str(self.id),
            "customer_code": self.partner_id.x_pastel_code,
            "invoice_date": self.invoice_date and self.invoice_date.isoformat(),
            "lines": [],
        }
        for line in self.invoice_line_ids:
            data["lines"].append({
                "name": line.name,
                "quantity": line.quantity,
                "price_unit": line.price_unit,
                "product_code": line.product_id.product_tmpl_id.x_pastel_item_code or line.product_id.default_code,
            })
        return data

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        if rec.move_type == "out_invoice" and self.env["pastel.sync.queue"]._push_enabled():
            self.env["pastel.sync.queue"].sudo().create({
                "model": "account.move",
                "res_id": rec.id,
                "operation": "create",
                "payload": json.dumps(rec._to_pastel_payload()),
            })
        return rec

    def write(self, vals):
        res = super().write(vals)
        if self.env["pastel.sync.queue"]._push_enabled():
            for rec in self.filtered(lambda m: m.move_type == "out_invoice"):
                self.env["pastel.sync.queue"].sudo().create({
                    "model": "account.move",
                    "res_id": rec.id,
                    "operation": "write",
                    "payload": json.dumps(
                        rec._to_pastel_payload() | {"external_key": rec.x_pastel_doc_no or str(rec.id)}
                    ),
                })
        return res

    def unlink(self):
        if self.env["pastel.sync.queue"]._push_enabled():
            for rec in self.filtered(lambda m: m.move_type == "out_invoice"):
                self.env["pastel.sync.queue"].sudo().create({
                    "model": "account.move",
                    "res_id": rec.id,
                    "operation": "unlink",
                    "payload": json.dumps({"doc_no": rec.x_pastel_doc_no or str(rec.id)}),
                })
        return super().unlink()


#
# import json, requests
# from odoo import models, fields, api
#
# class PastelSyncLog(models.Model):
#     _name = "pastel.sync.log"
#     _description = "Pastel Sync History"
#     _order = "create_date desc"
#
#     kind = fields.Selection([("customer","Customer"),("product","Product"),("invoice","Invoice")], required=True)
#     imported = fields.Integer(default=0)
#     updated = fields.Integer(default=0)
#     deleted = fields.Integer(default=0)
#     notes = fields.Char()
#     create_date = fields.Datetime(readonly=True)
#
# class PastelSyncQueue(models.Model):
#     _name = "pastel.sync.queue"
#     _description = "Pastel Sync Queue (push to Sage)"
#     _order = "id asc"
#
#     model = fields.Char(required=True)
#     res_id = fields.Integer(required=True)
#     operation = fields.Selection([("create","Create"),("write","Write"),("unlink","Unlink")], required=True)
#     payload = fields.Text()  # JSON
#     state = fields.Selection([("pending","Pending"),("done","Done"),("error","Error")], default="pending")
#     error = fields.Text()
#
#     def _push_enabled(self):
#         S = self.env["pastel.connector.setting"].sudo().search([], limit=1)
#         return bool(S and S.enable_push_to_sage)
#
#     def process_queue(self, limit=50):
#         base, key = self.env["pastel.sync"]._conf()
#         processed = 0
#         for rec in self.search([("state","=","pending")], limit=limit):
#             try:
#                 if not self._push_enabled():
#                     rec.write({"state":"done","error":"Skipped: push disabled"}); processed += 1; continue
#
#                 data = json.loads(rec.payload or "{}")
#                 if rec.model == "res.partner":
#                     path = "/customers"
#                 elif rec.model == "product.template":
#                     path = "/products"
#                 elif rec.model == "account.move":
#                     path = "/invoices"
#                 else:
#                     rec.write({"state":"error","error":"Unsupported model"}); continue
#
#                 if rec.operation == "create":
#                     method, url = "POST", path
#                 elif rec.operation == "write":
#                     ext = data.get("external_key") or data.get("code") or data.get("doc_no") or rec.res_id
#                     method, url = "PUT", f"{path}/{ext}"
#                 else:
#                     ext = data.get("external_key") or data.get("code") or data.get("doc_no") or rec.res_id
#                     method, url = "DELETE", f"{path}/{ext}"
#
#                 self.env["pastel.sync"]._req(method, url, key, base, json=data)
#                 rec.write({"state":"done","error":False}); processed += 1
#
#             except requests.HTTPError as e:
#                 if getattr(e.response, "status_code", None) == 405:
#                     rec.write({"state":"done","error":"Skipped: bridge method not implemented (405)"})
#                     processed += 1
#                 else:
#                     rec.write({"state":"error","error":str(e)})
#             except Exception as e:
#                 rec.write({"state":"error","error":str(e)})
#         return processed
#
# # ---- Enqueue hooks to push Odoo edits/deletes ----
# class ResPartner(models.Model):
#     _inherit = "res.partner"
#
#     def _to_pastel_payload(self):
#         self.ensure_one()
#         return {
#             "code": self.x_pastel_code or self.ref or str(self.id),
#             "name": self.name,
#             "phone": self.phone,
#             "email": self.email,
#             "credit_limit": self.x_pastel_credit_limit,
#             "tax_code": self.x_pastel_tax_code,
#             "currency_code": self.x_pastel_currency_code,
#             "category": self.x_pastel_category,
#             "open_item": self.x_pastel_open_item,
#         }
#
#     @api.model
#     def create(self, vals):
#         rec = super().create(vals)
#         if self.env["pastel.sync.queue"]._push_enabled():
#             self.env["pastel.sync.queue"].sudo().create({
#                 "model":"res.partner","res_id": rec.id,"operation":"create",
#                 "payload": json.dumps(rec._to_pastel_payload()),
#             })
#         return rec
#
#     def write(self, vals):
#         res = super().write(vals)
#         if self.env["pastel.sync.queue"]._push_enabled():
#             for rec in self:
#                 self.env["pastel.sync.queue"].sudo().create({
#                     "model":"res.partner","res_id": rec.id,"operation":"write",
#                     "payload": json.dumps(rec._to_pastel_payload() | {"external_key": rec.x_pastel_code or rec.ref or str(rec.id)}),
#                 })
#         return res
#
#     def unlink(self):
#         if self.env["pastel.sync.queue"]._push_enabled():
#             for rec in self:
#                 self.env["pastel.sync.queue"].sudo().create({
#                     "model":"res.partner","res_id": rec.id,"operation":"unlink",
#                     "payload": json.dumps({"code": rec.x_pastel_code or rec.ref or str(rec.id)}),
#                 })
#         return super().unlink()
#
# class ProductTemplate(models.Model):
#     _inherit = "product.template"
#
#     def _to_pastel_payload(self):
#         self.ensure_one()
#         return {
#             "code": self.x_pastel_item_code or self.default_code or str(self.id),
#             "name": self.name,
#             "tax_code": self.x_pastel_tax_code,
#             "price_regime": self.x_pastel_price_regime,
#         }
#
#     @api.model
#     def create(self, vals):
#         rec = super().create(vals)
#         if self.env["pastel.sync.queue"]._push_enabled():
#             self.env["pastel.sync.queue"].sudo().create({
#                 "model":"product.template","res_id": rec.id,"operation":"create",
#                 "payload": json.dumps(rec._to_pastel_payload()),
#             })
#         return rec
#
#     def write(self, vals):
#         res = super().write(vals)
#         if self.env["pastel.sync.queue"]._push_enabled():
#             for rec in self:
#                 self.env["pastel.sync.queue"].sudo().create({
#                     "model":"product.template","res_id": rec.id,"operation":"write",
#                     "payload": json.dumps(rec._to_pastel_payload() | {"external_key": rec.x_pastel_item_code or self.default_code or str(rec.id)}),
#                 })
#         return res
#
#     def unlink(self):
#         if self.env["pastel.sync.queue"]._push_enabled():
#             for rec in self:
#                 self.env["pastel.sync.queue"].sudo().create({
#                     "model":"product.template","res_id": rec.id,"operation":"unlink",
#                     "payload": json.dumps({"code": rec.x_pastel_item_code or rec.default_code or str(rec.id)}),
#                 })
#         return super().unlink()
#
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     def _to_pastel_payload(self):
#         self.ensure_one()
#         data = {
#             "doc_no": self.x_pastel_doc_no or str(self.id),
#             "customer_code": self.partner_id.x_pastel_code,
#             "invoice_date": self.invoice_date and self.invoice_date.isoformat(),
#             "lines": []
#         }
#         for line in self.invoice_line_ids:
#             data["lines"].append({
#                 "name": line.name,
#                 "quantity": line.quantity,
#                 "price_unit": line.price_unit,
#                 "product_code": line.product_id.product_tmpl_id.x_pastel_item_code or line.product_id.default_code,
#             })
#         return data
#
#     @api.model
#     def create(self, vals):
#         rec = super().create(vals)
#         if rec.move_type == "out_invoice" and self.env["pastel.sync.queue"]._push_enabled():
#             self.env["pastel.sync.queue"].sudo().create({
#                 "model":"account.move","res_id": rec.id,"operation":"create",
#                 "payload": json.dumps(rec._to_pastel_payload()),
#             })
#         return rec
#
#     def write(self, vals):
#         res = super().write(vals)
#         if self.env["pastel.sync.queue"]._push_enabled():
#             for rec in self.filtered(lambda m: m.move_type == "out_invoice"):
#                 self.env["pastel.sync.queue"].sudo().create({
#                     "model":"account.move","res_id": rec.id,"operation":"write",
#                     "payload": json.dumps(rec._to_pastel_payload() | {"external_key": rec.x_pastel_doc_no or str(rec.id)}),
#                 })
#         return res
#
#     def unlink(self):
#         if self.env["pastel.sync.queue"]._push_enabled():
#             for rec in self.filtered(lambda m: m.move_type == "out_invoice"):
#                 self.env["pastel.sync.queue"].sudo().create({
#                     "model":"account.move","res_id": rec.id,"operation":"unlink",
#                     "payload": json.dumps({"doc_no": rec.x_pastel_doc_no or str(rec.id)}),
#                 })
#         return super().unlink()
