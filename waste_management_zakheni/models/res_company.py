# models/res_company.py
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    # Services (service_requested_id on waste.service.request)
    wmz_service_ids = fields.Many2many(
        "service.request",
        "wmz_company_service_rel",
        "company_id",
        "service_id",
        string="Waste Services for Company",
        help="Which service offerings this company uses on Waste Service Requests."
    )

    # Container types (container_type_id on waste.service.request)
    wmz_container_type_ids = fields.Many2many(
        "container.type",
        "wmz_company_container_type_rel",
        "company_id",
        "container_type_id",
        string="Container Types for Company",
        help="Which container types (Bins/Tanks) this company is configured for."
    )
