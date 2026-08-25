"""Inject POPIA-safe partner domains into window actions at load time."""

from odoo import models


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    def read(self, fields=None, load="_classic_read"):
        result = super().read(fields, load=load)
        contacts = self.env.ref("contacts.action_contacts", raise_if_not_found=False)
        if not contacts:
            return result
        partner_model = self.env["res.partner"]
        for values in result:
            if (
                values.get("id") == contacts.id
                and values.get("res_model") == "res.partner"
            ):
                values["domain"] = partner_model._wmz_contacts_domain_list()
        return result
