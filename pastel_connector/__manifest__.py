{
    "name": "Pastel Partner Connector",
    "version": "1.0",
    "summary": "Standalone app: Import Customers, Products, Sales Invoices + History + Two-way sync queue",
    "depends": ["base", "contacts", "product", "account"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/pastel_config_views.xml",
        "views/pastel_import_form_views.xml",
        "views/pastel_history_views.xml",
        "views/pastel_queue_views.xml",
        "views/pastel_partner_inherit_views.xml",
        "views/pastel_product_inherit_views.xml",
        "views/pastel_invoice_inherit_views.xml",
        "views/account_move_pastel_export.xml",
        "data/pastel_config_data.xml",
        "views/pastel_menu.xml"
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
