{
    "name": "Pastel Batch Payment",
    "version": "17.0.1.0",
    "category": "Accounting",
    "summary": "Create & export batch payments to Sage Pastel via bridge",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/account_move_views.xml",
        "views/account_payment_views.xml",
        "wizard/batch_payment_add_wizard_views.xml",
        "views/res_config_settings_views.xml",
        "views/batch_payment_views.xml",

    ],
    "application": False,
    "installable": True,
    "license": "LGPL-3"
}
