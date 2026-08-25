from odoo import api, models

_WMZ_PROVIDER_MANAGER_GROUPS = (
    "base.group_system,"
    "waste_management_zakheni.group_company_admin,"
    "waste_management_zakheni.group_central_admin,"
    "waste_management_zakheni.group_wmz_admin,"
    "waste_management_zakheni.group_wmz_finance"
)


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    @api.model
    def _wmz_restore_provider_company_rule(self):
        """Restore Odoo default: each company only sees its own providers."""
        rule = self.env.ref("payment.payment_provider_company_rule", raise_if_not_found=False)
        if not rule:
            return
        defaults = {
            "name": "Access providers in own companies only",
            "domain_force": "[('company_id', 'parent_of', company_ids)]",
        }
        if rule.name != defaults["name"] or rule.domain_force != defaults["domain_force"]:
            rule.sudo().write(defaults)

    @api.model
    def _wmz_open_stripe_credential_groups(self):
        """Let company admins open Stripe forms without Settings (base.group_system).

        Stripe secret fields are Settings-only by default. The form still evaluates
        them in invisible= expressions, which crashes Owl for other users.
        """
        for fname in ("stripe_secret_key", "stripe_webhook_secret"):
            field = self._fields.get(fname)
            if field is not None:
                field.groups = _WMZ_PROVIDER_MANAGER_GROUPS

    @api.model
    def _wmz_company_has_portal_pay_provider(self, company):
        """Return True if the company already has a usable online payment provider."""
        return bool(self.env["payment.provider"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "in", ["enabled", "test"]),
            ("is_published", "=", True),
            ("code", "!=", "none"),
            ("module_state", "=", "installed"),
        ], limit=1))

    @api.model
    def _wmz_activate_portal_payment_providers(self):
        """Enable Demo (test mode) on portal-pay companies with no active provider."""
        Provider = self.env["payment.provider"].sudo()
        for company in self.env["res.company"].sudo().search([
            ("portal_confirmation_pay", "=", True),
        ]):
            if self._wmz_company_has_portal_pay_provider(company):
                continue
            demo = Provider.search([
                ("company_id", "=", company.id),
                ("code", "=", "demo"),
                ("module_state", "=", "installed"),
            ], limit=1)
            if not demo:
                continue
            demo.write({"state": "test", "is_published": True})
            demo._activate_default_pms()

    @api.model
    def _wmz_backfill_providers_from_master_company(self):
        """Copy installed providers from Zakheni ICT to sibling companies."""
        self._wmz_restore_provider_company_rule()
        self._wmz_open_stripe_credential_groups()
        Provider = self.env["payment.provider"].sudo()
        master = self.env["res.company"].sudo().search(
            [("name", "ilike", "zakheni")], order="id", limit=1
        )
        if not master:
            master = Provider.search(
                [("module_state", "=", "installed"), ("code", "!=", "none")],
                order="id",
                limit=1,
            ).company_id
        if not master:
            return

        templates = Provider.search([
            ("company_id", "=", master.id),
            ("module_state", "=", "installed"),
            ("code", "!=", "none"),
        ])
        if not templates:
            return

        for company in self.env["res.company"].sudo().search([("id", "!=", master.id)]):
            for template in templates:
                exists = Provider.search([
                    ("company_id", "=", company.id),
                    ("code", "=", template.code),
                ], limit=1)
                if exists:
                    continue
                copy_vals = {
                    "company_id": company.id,
                    "website_id": False,
                }
                if template.state in ("enabled", "test"):
                    copy_vals["state"] = template.state
                    copy_vals["is_published"] = template.is_published
                new_provider = template.with_context(
                    stripe_connect_onboarding=True,
                ).copy(copy_vals)
                if new_provider.state in ("enabled", "test"):
                    new_provider._activate_default_pms()

        self._wmz_activate_portal_payment_providers()

    def _register_hook(self):
        super()._register_hook()
        self._wmz_restore_provider_company_rule()
        self._wmz_open_stripe_credential_groups()
