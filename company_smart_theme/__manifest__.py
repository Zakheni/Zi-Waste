{
    "name": "Company Smart Theme",
    "version": "17.0.2.0.0",
    "summary": "Dynamic backend theme per company and user based on logo or custom color for Odoo 17 (OWL)",
    "author": "Lesiba Dev",
    "category": "Tools",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [
        "views/res_company_views.xml",
        "views/res_users_views.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "company_smart_theme/static/src/js/dynamic_theme.js"
        ]
    },
    "installable": True,
    "application": False
}
