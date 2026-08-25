"""Menu visibility overrides for WMZ driver users."""

from odoo import api, models

# Menus hidden for Driver role (Super Admin keeps full access).
DRIVER_HIDDEN_MENU_XMLIDS = (
    'waste_management_zakheni.menu_wmz_company_branches',
    'waste_management_zakheni.menu_service_request_user',
    'waste_management_zakheni.menu_waste_service',
    'waste_management_zakheni.menu_wmz_driver_waste_service',
    'contacts.menu_contacts',
    'spreadsheet_dashboard.spreadsheet_dashboard_menu_root',
)


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _wmz_worksheet_dashboard_menu_ids(self):
        """Retired OWL Worksheet Dashboard menus (removed from all users)."""
        return set(self.with_context(active_test=False).search([
            ('name', 'ilike', 'Worksheet Dashboard'),
        ]).ids)

    @api.model
    def _wmz_retired_worksheet_menu_ids(self):
        """Menus/actions retired in favour of one Worksheet menu + record rules."""
        Menu = self.with_context(active_test=False)
        retired = Menu.search([
            ('name', 'in', ('My Worksheets', 'All Worksheets', 'Worksheet Dashboard')),
        ])
        return set(retired.ids)

    @api.model
    def wmz_cleanup_worksheet_dashboard(self):
        """Remove retired OWL Worksheet Dashboard menu, action, and group."""
        Menu = self.with_context(active_test=False)

        actions = self.env['ir.actions.client'].search([
            '|',
            ('tag', '=', 'waste_management_zakheni.worksheet_dashboard'),
            ('name', 'ilike', 'Worksheet Dashboard'),
        ])
        menus = Menu.search([('name', 'ilike', 'Worksheet Dashboard')])
        if actions:
            action_refs = [f'ir.actions.client,{action.id}' for action in actions]
            menus |= Menu.search([('action', 'in', action_refs)])
            actions.unlink()
        if menus:
            menus.unlink()

        groups = self.env['res.groups'].with_context(active_test=False).search([
            ('name', 'ilike', 'Worksheet Dashboard'),
        ])
        if groups:
            groups.unlink()

        for xmlid in (
            'waste_management_zakheni.menu_worksheet_dashboard',
            'waste_management_zakheni.action_worksheet_dashboard',
            'waste_management_zakheni.group_wmz_worksheet_dashboard',
            'waste_management_zakheni.menu_waste_worksheet_driver',
            'waste_management_zakheni.menu_waste_worksheet_company_admin',
            'waste_management_zakheni.action_waste_worksheet_driver',
        ):
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record:
                record.unlink()

        root = self.env.ref('waste_management_zakheni.menu_pickup_root', raise_if_not_found=False)
        if root:
            Menu.search([
                ('name', 'in', ('My Worksheets', 'All Worksheets')),
            ]).unlink()
            root.write({'sequence': root.sequence})

        worksheet_menu = self.env.ref(
            'waste_management_zakheni.menu_waste_worksheet',
            raise_if_not_found=False,
        )
        if worksheet_menu:
            worksheet_menu.write({'name': 'Worksheet'})
        worksheet_action = self.env.ref(
            'waste_management_zakheni.action_waste_worksheet',
            raise_if_not_found=False,
        )
        if worksheet_action:
            worksheet_action.write({'name': 'Worksheet'})

        self.env.registry.clear_cache()

    @api.model
    def wmz_clear_web_assets(self):
        """Clear cached WMZ asset bundles only (do not wipe other module themes)."""
        attachments = self.env['ir.attachment'].sudo().search([
            ('public', '=', True),
            ('url', '=like', '/web/assets/%'),
            ('name', 'ilike', 'waste_management_zakheni'),
        ])
        if attachments:
            attachments.unlink()
        self.env.registry.clear_cache()

    @api.model
    def wmz_refresh_manifest_views(self):
        """Bust view cache for the manifest form after UI upgrades."""
        view = self.env.ref(
            'waste_management_zakheni.view_form_service_request',
            raise_if_not_found=False,
        )
        if view and view.arch_db:
            view.write({'arch_db': view.arch_db})
        self.env['ir.ui.view'].clear_caches()
        self.env.registry.clear_cache()

    @api.model
    def wmz_fix_worksheet_security(self):
        """Repair worksheet ACL groups and recompute driver partner links after upgrade."""
        full_access_xmlids = (
            'waste_management_zakheni.group_wmz_admin',
            'waste_management_zakheni.group_wmz_admin_clerk',
            'waste_management_zakheni.group_wmz_manager',
            'waste_management_zakheni.group_wmz_finance',
            'waste_management_zakheni.group_company_admin',
            'waste_management_zakheni.group_central_admin',
        )
        full_access_groups = self.env['res.groups']
        for xmlid in full_access_xmlids:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                full_access_groups |= group

        for rule_xmlid in (
            'waste_management_zakheni.waste_worksheet_company_rule',
            'waste_management_zakheni.waste_worksheet_multi_company_rule',
        ):
            rule = self.env.ref(rule_xmlid, raise_if_not_found=False)
            if rule and full_access_groups:
                rule.write({'groups': [(6, 0, full_access_groups.ids)]})

        driver_rule = self.env.ref(
            'waste_management_zakheni.wmz_rule_worksheet_driver',
            raise_if_not_found=False,
        )
        rule_domains = {
            'waste_management_zakheni.wmz_rule_worksheet_driver': (
                "[('company_id', '=', user.company_id.id), "
                "('driver_id', '=', user.partner_id.id)]"
            ),
            'waste_management_zakheni.wmz_rule_manifest_driver': (
                "[('state', 'in', ['scheduled', 'dispatched', 'service_delivered', 'done']), "
                "('company_id', '=', user.company_id.id), "
                "('driver_id', '=', user.partner_id.id)]"
            ),
            'waste_management_zakheni.wmz_rule_vehicle_inspection_driver': (
                "['|', ('inspector_id', '=', user.id), "
                "('driver_id', '=', user.partner_id.id)]"
            ),
        }
        for rule_xmlid, domain_force in rule_domains.items():
            rule = self.env.ref(rule_xmlid, raise_if_not_found=False)
            if rule:
                rule.write({'domain_force': domain_force})

        driver_group = self.env.ref(
            'waste_management_zakheni.group_wmz_driver',
            raise_if_not_found=False,
        )
        if driver_group:
            self.env['res.users'].search([
                ('groups_id', 'in', driver_group.id),
            ])._compute_wmz_driver_partner_ids()

        self.env.registry.clear_cache()

    def _register_hook(self):
        super()._register_hook()
        self.wmz_cleanup_worksheet_dashboard()
        self.wmz_fix_worksheet_security()

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug=debug)
        visible -= self._wmz_worksheet_dashboard_menu_ids()
        visible -= self._wmz_retired_worksheet_menu_ids()

        user = self.env.user
        if user._is_public() or user._is_portal():
            return visible
        if not user.has_group('waste_management_zakheni.group_wmz_driver'):
            return visible
        if user.has_group('waste_management_zakheni.group_wmz_admin'):
            return visible

        hidden_ids = set()
        for xmlid in DRIVER_HIDDEN_MENU_XMLIDS:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                hidden_ids.add(menu.id)
        return visible - hidden_ids
