{
    "name": "Company Smart Theme",
    "version": "17.0.2.0.32",
    "post_init_hook": "post_init_hook",
    "summary": "Dynamic backend theme per company and user based on logo or custom color for Odoo 17 (OWL)",
    "author": "Lesiba Dev",
    "category": "Tools",
    "license": "LGPL-3",
    "depends": ["base", "web", "mail"],
    "external_dependencies": {"python": ["Pillow", "colorthief"]},
    "data": [
        "data/theme_sync.xml",
        "views/res_company_views.xml",
        "views/res_users_views.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "company_smart_theme/static/src/js/theme_config.js",
            "company_smart_theme/static/src/js/color_scheme_service.js",
            "company_smart_theme/static/src/systray/dark_mode_systray.scss",
            "company_smart_theme/static/src/systray/dark_mode_systray.xml",
            "company_smart_theme/static/src/systray/dark_mode_systray.js",
            "company_smart_theme/static/src/fields/theme_palette_picker/theme_palette_picker_field.scss",
            "company_smart_theme/static/src/fields/theme_palette_picker/theme_palette_picker_field.xml",
            "company_smart_theme/static/src/fields/theme_palette_picker/theme_palette_picker_field.js",
            "company_smart_theme/static/src/js/dynamic_theme.js",
            "company_smart_theme/static/src/css/widgets.css",
            "company_smart_theme/static/src/scss/stat_buttons.scss",
            "company_smart_theme/static/src/scss/manifest_alerts.scss",
            "company_smart_theme/static/src/scss/chatter.scss",
            "company_smart_theme/static/src/scss/list_view.scss",
        ]
    },
    "installable": True,
    "application": False
}
