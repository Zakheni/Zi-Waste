# from odoo import models, fields, _
# from odoo.exceptions import UserError
#
# # ------------------------------------------------------------------------------
# # Connector settings (unchanged API, just doc/help polish)
# # ------------------------------------------------------------------------------
# class PastelConnectorSetting(models.Model):
#     _name = "pastel.connector.setting"
#     _description = "Pastel Connector Settings"
#     _rec_name = "name"
#
#     name = fields.Char(default="Pastel Connector Configuration", readonly=True)
#     pastel_api_base = fields.Char(
#         string="Bridge URL",
#         required=True,
#         help="Base URL of the FastAPI bridge, e.g. http://WINDOWS-IP:8787",
#     )
#     pastel_api_key = fields.Char(
#         string="API Key",
#         required=True,
#         help="x-api-key used by the bridge",
#     )
#     enable_push_to_sage = fields.Boolean(
#         string="Enable push (Odoo → Sage)",
#         default=False,
#         help="If enabled, Odoo edits/deletes will be pushed to Sage via the bridge",
#     )
#
#     def action_test_connection(self):
#         self.ensure_one()
#         ok = self.env["pastel.sync"].pastel_test_connection()
#         if ok:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {"title": _("Pastel"), "message": _("Connection OK"), "type": "success"},
#             }
#         raise UserError(_("Connection failed"))
#
#     def action_import_all_now(self):
#         self.ensure_one()
#         res = self.env["pastel.sync"].import_all(customers=True, products=True, invoices=True)
#         msg = _("Imported: Cust %(ci)s/%(cu)s updated, Prod %(pi)s/%(pu)s updated, Inv %(ii)s/%(iu)s updated") % res
#         return {
#             "type": "ir.actions.client",
#             "tag": "display_notification",
#             "params": {"title": _("Pastel Import"), "message": msg, "type": "success"},
#         }
#
#
# # ------------------------------------------------------------------------------
# # CUSTOMERS (res.partner)
# # Mapping to bridge /customers JSON (examples in comments)
# # {
# #   "code": "C0001", "name": "...", "phone": "...", "email": "...",
# #   "credit_limit": 10000, "balance": 1500, "tax_code": "15",
# #   "address1": "...", "address2": "...", "postal_code": "...",
# #   "country_code": "ZA", "currency_code": "ZAR",
# #   "settlement_terms": "...", "payment_terms": "...",
# #   "discount_percent": 5.0, "price_regime": "...",
# #   "updated_on": "2025-10-18", "guid": "..."
# # }
# # ------------------------------------------------------------------------------
# class ResPartner(models.Model):
#     _inherit = "res.partner"
#
#     # Identifiers / links
#     x_pastel_code = fields.Char(index=True, copy=False, string="Sage Customer Code")
#     x_pastel_guid = fields.Char(string="Sage GUID", copy=False)
#     x_pastel_updated_on = fields.Char(string="Sage Updated On", help="Raw value from Pastel (string/ISO)")
#
#     # Accounting / commercial
#     x_pastel_tax_code = fields.Char(string="Sage Tax Code")
#     x_pastel_currency_code = fields.Char(string="Sage Currency")
#     x_pastel_credit_limit = fields.Float(string="Sage Credit Limit", copy=False)
#     x_pastel_balance = fields.Float(string="Sage Current Balance", copy=False)
#     x_pastel_settlement_terms = fields.Char(string="Sage Settlement Terms")
#     x_pastel_payment_terms = fields.Char(string="Sage Payment Terms")
#     x_pastel_discount_percent = fields.Float(string="Sage Discount %")
#     x_pastel_price_regime = fields.Char(string="Sage Price Regime")
#     x_pastel_open_item = fields.Boolean(string="Sage Open Item")
#     x_pastel_category = fields.Char(string="Sage Category")
#
#     # Address/contact (Odoo already has standard fields; we store extras for traceability)
#     x_pastel_addr1 = fields.Char(string="Sage Address 1")
#     x_pastel_addr2 = fields.Char(string="Sage Address 2")
#     x_pastel_addr3 = fields.Char(string="Sage Address 3")
#     x_pastel_addr4 = fields.Char(string="Sage Address 4")
#     x_pastel_postal_code = fields.Char(string="Sage Postal Code")
#     x_pastel_country_code = fields.Char(string="Sage Country Code")
#
#     # Bank / identity (optional; do not auto-fill in Odoo’s bank/journal without explicit choice)
#     x_pastel_bank_name = fields.Char(string="Sage Bank Name")
#     x_pastel_bank_type = fields.Char(string="Sage Bank Type")
#     x_pastel_bank_branch = fields.Char(string="Sage Bank Branch")
#     x_pastel_bank_account = fields.Char(string="Sage Bank Account")
#     x_pastel_first_name = fields.Char(string="Sage First Name")
#     x_pastel_last_name = fields.Char(string="Sage Last Name")
#     x_pastel_id_number = fields.Char(string="Sage ID Number")
#     x_pastel_passport = fields.Char(string="Sage Passport")
#     x_pastel_sole_proprietor = fields.Boolean(string="Sage Sole Proprietor")
#     x_pastel_third_party_id = fields.Char(string="Sage Third Party ID")
#
#
# # ------------------------------------------------------------------------------
# # PRODUCTS (product.template)
# # Mapping to bridge /products JSON
# # {
# #   "code":"ITEM001","name":"...","category":"...","barcode":"...",
# #   "unit_size":"EA","tax_code":"15","gl_code":"4000","allow_tax":true,
# #   "weight":0.35,"cost_price":100,"price_1":120,...,"qty_on_hand":5,
# #   "reorder_level":2,"custom_text1":"...","updated_on":"...", "guid":"..."
# # }
# # ------------------------------------------------------------------------------
# class ProductTemplate(models.Model):
#     _inherit = "product.template"
#
#     # Identifiers / links
#     x_pastel_item_code = fields.Char(index=True, string="Sage Item Code")
#     x_pastel_guid = fields.Char(string="Sage GUID", copy=False)
#     x_pastel_updated_on = fields.Char(string="Sage Updated On")
#
#     # Classification / references
#     x_pastel_category = fields.Char(string="Sage Category")
#     x_pastel_unit_size = fields.Char(string="Sage Unit Size")
#     x_pastel_gl_code = fields.Char(string="Sage Sales GL Code")
#
#     # Taxes / flags
#     x_pastel_tax_code = fields.Char(string="Sage Tax Code")
#     x_pastel_allow_tax = fields.Char(string="Sage Allow Tax (raw)")
#
#     # Prices / costs
#     x_pastel_cost_price = fields.Float(string="Sage Cost Price")
#     x_pastel_price_1 = fields.Float(string="Sage Selling Price 1")
#     x_pastel_price_2 = fields.Float(string="Sage Selling Price 2")
#     x_pastel_price_3 = fields.Float(string="Sage Selling Price 3")
#     x_pastel_price_4 = fields.Float(string="Sage Selling Price 4")
#     x_pastel_price_5 = fields.Float(string="Sage Selling Price 5")
#
#     # Inventory levels
#     x_pastel_qty_on_hand = fields.Float(string="Sage Qty On Hand")
#     x_pastel_qty_on_order = fields.Float(string="Sage Qty On Order")
#     x_pastel_reorder_level = fields.Float(string="Sage Reorder Level")
#
#     # Misc
#     x_pastel_weight = fields.Float(string="Sage Nett Mass / Weight")
#     x_pastel_custom_text1 = fields.Char(string="Sage Custom Text 1")
#
#
# # ------------------------------------------------------------------------------
# # INVOICES (account.move + account.move.line)
# # Mapping to bridge /invoices JSON
# # {
# #   "doc_no":"000123","invoice_date":"2025-01-20","customer_code":"C0001",
# #   "amount_total":1150.0,"amount_total_excl":1000.0,"tax_amount":150.0,
# #   "document_type":1,
# #   "lines":[{"product_code":"ITEM001","name":"...","quantity":2,"price_unit":500,"tax_code":"15"}]
# # }
# # ------------------------------------------------------------------------------
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     x_pastel_doc_no = fields.Char(string="Sage Doc No.", index=True, help="HistoryHeader.DocumentNumber")
#     x_pastel_document_type = fields.Integer(string="Sage DocumentType")
#     x_pastel_excl_incl = fields.Char(string="Sage Excl/Incl (raw)")
#     x_pastel_tax_amount = fields.Float(string="Sage Header Tax Amount")
#     x_pastel_amount_total_excl = fields.Float(string="Sage Total Excl")
#     x_pastel_amount_total_incl = fields.Float(string="Sage Total Incl")

#
# class AccountMoveLine(models.Model):
#     _inherit = "account.move.line"
#
#     x_pastel_product_code = fields.Char(string="Sage Item Code (line)")
#     x_pastel_tax_code = fields.Char(string="Sage Tax Code (line)")


from odoo import models, fields, _
from odoo.exceptions import UserError

class PastelConnectorSetting(models.Model):
    _name = "pastel.connector.setting"
    _description = "Pastel Connector Settings"
    _rec_name = "name"

    name = fields.Char(default="Pastel Connector Configuration", readonly=True)
    pastel_api_base = fields.Char(string="Bridge URL", required=True, help="e.g. http://WINDOWS-IP:8787")
    pastel_api_key  = fields.Char(string="API Key", required=True)
    enable_push_to_sage = fields.Boolean(string="Enable push (Odoo → Sage)", default=True,
                                         help="If enabled, Odoo edits/deletes will be pushed to Sage via the bridge")

    def action_test_connection(self):
        self.ensure_one()
        ok = self.env["pastel.sync"].pastel_test_connection()
        if ok:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Pastel"), "message": _("Connection OK"), "type": "success"},
            }
        raise UserError(_("Connection failed"))

    def action_import_all_now(self):
        self.ensure_one()
        res = self.env["pastel.sync"].import_all(customers=True, products=True, invoices=True)
        msg = _("Imported: Cust %(ci)s/%(cu)s updated, Prod %(pi)s/%(pu)s updated, Inv %(ii)s/%(iu)s updated") % res
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Pastel Import"), "message": msg, "type": "success"},
        }

# Extra "Sage" fields on Odoo core models for visibility/mapping
class ResPartner(models.Model):
    _inherit = "res.partner"
    x_pastel_code = fields.Char(index=True, copy=False, string="Sage Customer Code")
    x_pastel_tax_code = fields.Char(string="Sage Tax Code")
    x_pastel_category = fields.Char(string="Sage Category")
    x_pastel_currency_code = fields.Char(string="Sage Currency")
    x_pastel_open_item = fields.Boolean(string="Sage Open Item")
    x_pastel_credit_limit = fields.Float(string="Sage Credit Limit", copy=False)
    x_pastel_balance = fields.Float(string="Sage Current Balance", copy=False)


class ProductTemplate(models.Model):
    _inherit = "product.template"
    x_pastel_item_code = fields.Char(index=True, string="Sage Item Code")
    x_pastel_price_regime = fields.Char(string="Sage Price Regime")
    x_pastel_tax_code = fields.Char(string="Sage Tax Code")

class AccountMove(models.Model):
    _inherit = "account.move"
    x_pastel_doc_no = fields.Char(string="Sage Doc No.", index=True)
    x_pastel_status = fields.Char(string="Sage Status")
