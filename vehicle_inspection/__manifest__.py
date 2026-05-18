{
    "name": "Vehicle Inspection Management",
    "version": "17.0.1.0.0",
    "category": "Fleet",
    "summary": "Internal Fleet and Garage Vehicle Inspections",
    "depends": [
        "base",
        "fleet",
        "mail",
    ],

    'data': [
        # security / data
        'security/vehicle_inspection_groups.xml',
        'security/vehicle_inspection_rules.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/inspection_cron.xml',
        'data/mail_template_not_running.xml',
        'data/mail_template_fault.xml',
        'data/mail_template_resolved.xml',
        'data/mail_template_resolved_not_running.xml',

        # reports
        'report/inspection_report.xml',
        'report/inspection_report_template.xml',

        'views/inspection_line_views.xml',
        'views/inspection_category_views.xml',
        'views/inspection_item_views.xml',
        'views/vehicle_inspection_views.xml',
        'views/vehicle_fault_wizard_views.xml',
        'views/vehicle_not_running_wizard_views.xml',
        'views/vehicle_resolved_wizard_views.xml',
        'views/vehicle_resolved_not_running_wizard_views.xml',
        'views/fleet_vehicle_views.xml',

        # MENU MUST BE LAST
        'views/menu.xml',
    ]
    ,
    # "assets": {
    #     "web.assets_backend": [
    #         "vehicle_inspection/static/src/dashboard/vehicle_inspection_dashboard.js",
    #         "vehicle_inspection/static/src/dashboard/vehicle_inspection_dashboard.xml",
    #     ],
    # },
    "application": True,
}
