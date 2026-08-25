"""Tax and journal mappings from Odoo to Sage codes."""

from odoo import api, fields, models


class SageMappingTax(models.Model):
    """Map an Odoo tax to a Sage tax code."""

    _name = "sage.mapping.tax"
    _description = "Sage Tax Mapping"
    _rec_name = "display_name"

    backend_id = fields.Many2one("sage.backend", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="backend_id.company_id", store=True)
    tax_id = fields.Many2one("account.tax", required=True, ondelete="cascade")
    sage_tax_code = fields.Char(required=True)
    notes = fields.Char()
    display_name = fields.Char(compute="_compute_display_name", store=True)

    _sql_constraints = [
        ("tax_backend_uniq", "unique(backend_id, tax_id)", "Each tax can only be mapped once per backend."),
    ]

    @api.depends("tax_id", "sage_tax_code")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s → %s" % (rec.tax_id.display_name or "Tax", rec.sage_tax_code or "")


class SageMappingJournal(models.Model):
    """Map an Odoo journal to a Sage cashbook / receipt bank code."""

    _name = "sage.mapping.journal"
    _description = "Sage Journal Mapping"
    _rec_name = "display_name"

    backend_id = fields.Many2one("sage.backend", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="backend_id.company_id", store=True)
    journal_id = fields.Many2one("account.journal", required=True, ondelete="cascade")
    sage_journal_code = fields.Char(required=True, help="Sage cashbook / bank / receipt journal code")
    notes = fields.Char()
    display_name = fields.Char(compute="_compute_display_name", store=True)

    _sql_constraints = [
        ("journal_backend_uniq", "unique(backend_id, journal_id)", "Each journal can only be mapped once per backend."),
    ]

    @api.depends("journal_id", "sage_journal_code")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s → %s" % (rec.journal_id.display_name or "Journal", rec.sage_journal_code or "")
