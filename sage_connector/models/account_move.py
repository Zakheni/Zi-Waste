"""Sage document number on invoices plus export action."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    """Store Sage doc number and enqueue/process export."""

    _inherit = "account.move"

    sage_doc_no = fields.Char(string="Sage Document Number", index=True, copy=False)

    def init(self):
        cr = self.env.cr
        cr.execute("""
            SELECT COUNT(*) FROM (
                SELECT COALESCE(company_id, 0), sage_doc_no
                FROM account_move
                WHERE sage_doc_no IS NOT NULL AND sage_doc_no <> ''
                GROUP BY 1, 2 HAVING COUNT(*) > 1
            ) dup
        """)
        if cr.fetchone()[0]:
            return
        cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS account_move_sage_doc_no_uniq
            ON account_move (COALESCE(company_id, 0), sage_doc_no)
            WHERE sage_doc_no IS NOT NULL AND sage_doc_no <> ''
        """)

    @api.constrains("sage_doc_no", "company_id")
    def _check_sage_doc_no_unique(self):
        for rec in self:
            code = (rec.sage_doc_no or "").strip()
            if not code:
                continue
            domain = [
                ("sage_doc_no", "=", code),
                ("id", "!=", rec.id),
                ("company_id", "=", rec.company_id.id),
            ]
            if rec.search_count(domain):
                raise ValidationError(_("Sage document number %s is already used.") % code)

    def write(self, vals):
        if vals.get("x_pastel_doc_no") and "sage_doc_no" not in vals:
            vals = dict(vals, sage_doc_no=vals["x_pastel_doc_no"])
        if vals.get("sage_doc_no") and "x_pastel_doc_no" not in vals:
            vals = dict(vals, x_pastel_doc_no=vals["sage_doc_no"])
        return super().write(vals)

    def action_export_to_sage_connector(self):
        """Enqueue then process invoice export through sage.sync."""
        moves = self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund") and m.state == "posted")
        Job = self.env["sage.job"].sudo()
        exported, errors = 0, []
        for move in moves:
            try:
                backend = self.env["sage.backend"]._for_company(move.company_id)
                job = Job.enqueue(
                    backend,
                    "export_invoice",
                    res_model="account.move",
                    res_id=move.id,
                    idempotency_key="odoo-move-%s" % move.id,
                )
                job.action_process_now()
                exported += 1
            except Exception as exc:
                errors.append("%s: %s" % (move.display_name, exc))
        msg = _("Exported: %s") % exported
        if errors:
            msg += " — " + "; ".join(errors[:3])
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Sage"), "message": msg, "type": "warning" if errors else "success"},
        }
