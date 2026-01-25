{
    "name": "Vehicle Inspection Management",
    "version": "17.0.1.0.0",
    "category": "Fleet",
    "summary": "Internal Fleet and Garage Vehicle Inspections",
    "depends": [
        "base",
        "board",
        "fleet",
        "mail",
    ],

    'data': [
        # security / data
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/inspection_cron.xml',

        # reports
        'report/inspection_report.xml',
        'report/inspection_report_template.xml',

        # # DASHBOARD FIRST (creates board.board record + action)

        # 'views/vehicle_inspection_dashboard_action.xml',

        # normal views
        'views/inspection_line_views.xml',
        'views/inspection_category_views.xml',
        'views/inspection_item_views.xml',
        'views/vehicle_inspection_views.xml',

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
