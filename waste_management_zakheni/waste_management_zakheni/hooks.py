"""Post-install hooks for the Waste Management Zakheni module.

Seeds WMZ configuration records (services, waste types, container types,
etc.) from existing product attribute values after module installation.
"""
from odoo import api, SUPERUSER_ID


def _seed_config_from_attributes(env):
    """Create WMZ config records from product attribute values.

    For each mapped product attribute (e.g. *Waste Type*, *Container Type*),
    ensures a corresponding record exists in the target configuration model,
    linked via ``pav_id``.

    :param env: Odoo environment (typically from a post-init hook).
    :type env: odoo.api.Environment
    :return: None
    """
    mapping = {
        'Service Requested': 'service.request',
        'Waste Type':        'waste.type',
        'Waste Details':     'waste.details',
        'Bin Type':          'bin.type',
        'Tank Volume':       'tank.volume',
        'Container Type':    'container.type',
    }
    PAV = env['product.attribute.value']
    for attr_name, model_name in mapping.items():
        for pav in PAV.search([('attribute_id.name', '=', attr_name)]):
            if not env[model_name].search([('pav_id', '=', pav.id)], limit=1):
                env[model_name].create({'pav_id': pav.id, 'name': pav.name})


def _apply_green_brand_theme(env):
    """Apply Zakheni green as the global Odoo / website brand color."""
    env['res.company'].search([]).write({
        'primary_color': '#15803d',
        'secondary_color': '#166534',
    })
    if 'web_editor.assets' in env:
        assets = env['web_editor.assets']
        assets.make_scss_customization(
            '/website/static/src/scss/options/colors/user_theme_color_palette.scss',
            {'primary': '#15803d', 'secondary': '#166534'},
        )
        assets.make_scss_customization(
            '/website/static/src/scss/options/colors/user_color_palette.scss',
            {
                'o-color-1': '#15803d',
                'o-color-2': '#166534',
                'o-color-3': '#dcfce7',
                'o-color-4': '#ffffff',
                'o-color-5': '#14532d',
            },
        )


def post_init_seed_waste_config(env):
    """Post-install hook entry point for seeding WMZ configuration.

    Called automatically after module installation/upgrade. Delegates to
    :func:`_seed_config_from_attributes` to populate configuration models
    from product attribute values.

    :param env: Odoo environment provided by the post-init hook (Odoo 17 style).
    :type env: odoo.api.Environment
    :return: None
    """
    _seed_config_from_attributes(env)
    _apply_green_brand_theme(env)
    env['res.partner']._backfill_missing_customer_references()
    env['res.partner']._backfill_missing_company_ids()
    env['res.partner']._wmz_fix_system_partner_companies()
    env['res.partner']._wmz_fix_contacts_action_domain()
    env['wms.service.provider']._backfill_full_address()
    env['ir.ui.menu'].wmz_fix_worksheet_security()
    env['payment.provider']._wmz_backfill_providers_from_master_company()
    env['payment.provider']._wmz_activate_portal_payment_providers()
    env['res.company']._wmz_apply_portal_quotation_policy()
