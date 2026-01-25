from odoo import models, fields, _
import logging
import json
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

class PastelImportForm(models.Model):
    _name = "pastel.import.form"
    _description = "Pastel Import Settings (Form)"
    _rec_name = "name"


    name = fields.Char(default="Import from Sage", readonly=True)

    import_customers = fields.Boolean(string="Import Customers", default=True)
    import_products  = fields.Boolean(string="Import Products", default=True)
    import_invoices  = fields.Boolean(string="Import Sales Invoices", default=True)
    import_suppliers = fields.Boolean(string="Import Suppliers", default=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True
    )

    last_result = fields.Char(string="Last Result", readonly=True)

    # ---- helpers ----
    def _notify(self, title, msg, level="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": title, "message": msg, "type": level},
        }

    # ---- single imports ----
    def action_import_customers(self):
        self.ensure_one()
        res = self.env["pastel.sync"].import_all(customers=True, products=False, invoices=False, suppliers=False)
        msg = _("Customers imported: created %(ci)s, updated %(cu)s") % res
        self.write({"last_result": msg})
        return self._notify(_("Pastel Import"), msg)

    def action_import_products(self):
        self.ensure_one()
        res = self.env["pastel.sync"].import_all(customers=False, products=True, invoices=False, suppliers=False)
        msg = _("Products imported: created %(pi)s, updated %(pu)s") % res
        self.write({"last_result": msg})
        return self._notify(_("Pastel Import"), msg)

    def action_import_invoices(self):
        self.ensure_one()
        res = self.env["pastel.sync"].import_all(customers=False, products=False, invoices=True, suppliers=False)
        msg = _("Invoices imported: created %(ii)s, updated %(iu)s") % res
        self.write({"last_result": msg})
        return self._notify(_("Pastel Import"), msg)

    # def action_import_suppliers(self):
    #     self.ensure_one()
    #     res = self.env["pastel.sync"].import_all(customers=False, products=False, invoices=False, suppliers=True)
    #     # keys: si (created), su (updated)
    #     msg = _("Suppliers imported: created %(si)s, updated %(su)s") % res
    #     self.write({"last_result": msg})
    #     return self._notify(_("Pastel Import"), msg)



    # ---- import according to checkboxes ----
    def action_import_now(self):
        self.ensure_one()
        res = self.env["pastel.sync"].import_all(
            customers=self.import_customers,
            products=self.import_products,
            invoices=self.import_invoices,
            suppliers=self.import_suppliers,
        )
        msg = _(
            "Imported: Cust %(ci)s/%(cu)s, Prod %(pi)s/%(pu)s, Inv %(ii)s/%(iu)s, Sup %(si)s/%(su)s"
        ) % res
        self.write({"last_result": msg})
        return self._notify(_("Pastel Import"), msg)

    # ---- force all ----
    def action_import_all(self):
        self.ensure_one()
        res = self.env["pastel.sync"].import_all(customers=True, products=True, invoices=True, suppliers=True)
        msg = _(
            "Imported ALL: Cust %(ci)s/%(cu)s, Prod %(pi)s/%(pu)s, Inv %(ii)s/%(iu)s, Sup %(si)s/%(su)s"
        ) % res
        self.write({"last_result": msg})
        return self._notify(_("Pastel Import"), msg)

    def debug_fetch_suppliers(self, limit=10):
        """
        Fetch suppliers directly from the bridge (no create/update), just to
        prove the bridge returns data. Uses pastel.sync._conf/_req.
        """
        self.ensure_one()
        Sync = self.env["pastel.sync"].sudo()
        # >>> call the helper model, not the wizard
        base, key = Sync._conf()
        data = Sync._req("GET", f"/suppliers?limit={int(limit)}", key, base)

        if not isinstance(data, list):
            raise UserError(_("Unexpected response from bridge (not a list)."))

        # store a short sample in the wizard for inspection
        sample = data[: min(len(data), 5)]
        self.write({"last_result": json.dumps(sample, indent=2)})
        return self._notify(_("Pastel Bridge"),
                            _("Fetched %(n)s suppliers (showing up to 5).", n=len(data)),
                            "success")

    def action_import_suppliers(self):
        """
        Run the real import via pastel.sync.import_suppliers()
        (You can also call import_all(..., suppliers=True) if you like.)
        """
        self.ensure_one()
        Sync = self.env["pastel.sync"].sudo()
        res = Sync.import_suppliers()  # or: Sync.import_all(customers=False, products=False, invoices=False, suppliers=True)

        # res is expected like {"si": created, "su": updated}
        si = int(res.get("si", 0))
        su = int(res.get("su", 0))
        msg = _("Suppliers imported: created %(si)s, updated %(su)s", si=si, su=su)

        # keep a trace in the wizard
        self.write({"last_result": json.dumps(res, indent=2)})
        level = "success" if (si or su) else "warning"
        return self._notify(_("Pastel Import"), msg, level)


# from odoo import models, fields, api, _
#
# class PastelImportForm(models.Model):
#     _name = "pastel.import.form"
#     _description = "Pastel Import Settings (Form)"
#     _rec_name = "name"
#
#     name = fields.Char(default="Import from Sage", readonly=True)
#     import_customers = fields.Boolean(string="Import Customers", default=True)
#     import_products  = fields.Boolean(string="Import Products", default=True)
#     import_invoices  = fields.Boolean(string="Import Sales Invoices", default=True)
#
#     last_result = fields.Char(string="Last Result", readonly=True)
#
#     # ---- SINGLE IMPORTS ----
#     def _notify(self, title, msg, level="success"):
#         return {
#             "type": "ir.actions.client",
#             "tag": "display_notification",
#             "params": {"title": title, "message": msg, "type": level},
#         }
#
#     def action_import_customers(self):
#         self.ensure_one()
#         res = self.env["pastel.sync"].import_all(customers=True, products=False, invoices=False)
#         msg = _("Customers imported: created %(ci)s, updated %(cu)s") % res
#         self.write({"last_result": msg})
#         return self._notify(_("Pastel Import"), msg)
#
#     def action_import_products(self):
#         self.ensure_one()
#         res = self.env["pastel.sync"].import_all(customers=False, products=True, invoices=False)
#         msg = _("Products imported: created %(pi)s, updated %(pu)s") % res
#         self.write({"last_result": msg})
#         return self._notify(_("Pastel Import"), msg)
#
#     def action_import_invoices(self):
#         self.ensure_one()
#         res = self.env["pastel.sync"].import_all(customers=False, products=False, invoices=True)
#         msg = _("Invoices imported: created %(ii)s, updated %(iu)s") % res
#         self.write({"last_result": msg})
#         return self._notify(_("Pastel Import"), msg)
#
#     # ---- IMPORT ALL (respects checkboxes) ----
#     def action_import_now(self):
#         """Uses the three checkboxes to decide which to run."""
#         self.ensure_one()
#         res = self.env["pastel.sync"].import_all(
#             customers=self.import_customers,
#             products=self.import_products,
#             invoices=self.import_invoices,
#         )
#         msg = _("Imported: Cust %(ci)s/%(cu)s, Prod %(pi)s/%(pu)s, Inv %(ii)s/%(iu)s") % res
#         self.write({"last_result": msg})
#         return self._notify(_("Pastel Import"), msg)
#
#     # ---- IMPORT ALL (force all three regardless of checkboxes) ----
#     def action_import_all(self):
#         self.ensure_one()
#         res = self.env["pastel.sync"].import_all(customers=True, products=True, invoices=True)
#         msg = _("Imported ALL: Cust %(ci)s/%(cu)s, Prod %(pi)s/%(pu)s, Inv %(ii)s/%(iu)s") % res
#         self.write({"last_result": msg})
#         return self._notify(_("Pastel Import"), msg)
#
