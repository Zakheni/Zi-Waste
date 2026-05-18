# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    export_state = fields.Selection([
        ('not_exported', 'Not Exported'),
        ('exported', 'Exported(Single)')
    ], string="Export Status", default=False)

    def action_export_to_sage(self):

        moves = self.filtered(
            lambda m: m.move_type in ("out_invoice", "out_refund")
            and m.state == "posted"
        )

        if not moves:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Export to Sage"),
                    "message": _("No posted invoices to export."),
                    "type": "warning",
                },
            }

        exported = 0
        skipped = 0
        errs = []

        payment_journal = self.env["account.journal"].search(
            [("type", "=", "bank")],
            limit=1
        )

        if not payment_journal:
            raise UserError(_("Please configure a bank journal."))

        for move in moves.sudo():
            try:

                # EXPORT TO SAGE
                self.env["pastel.sync"].export_invoice(move.id)

                # CREATE PAYMENT
                payment_register = self.env[
                    "account.payment.register"
                ].with_context(
                    active_model="account.move",
                    active_ids=move.ids,
                ).create({
                    "journal_id": payment_journal.id,
                    "amount": move.amount_residual,
                })

                payment_register._create_payments()

                # MARK AS EXPORTED
                # move.is_exported = True
                move.export_state = 'exported'

                exported += 1

            except Exception as e:
                skipped += 1
                errs.append(f"{move.display_name}: {str(e)}")
                _logger.exception("Export failed")

        base_msg = _("Exported: %(e)s, Skipped: %(s)s") % {
            "e": exported,
            "s": skipped,
        }

        msg = base_msg

        if errs:
            msg += " - " + "; ".join(errs[:3])

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Export to Sage"),
                "message": msg,
                "type": "warning" if errs else "success",
            },
        }


# # -*- coding: utf-8 -*-
# import logging
# from odoo import models, _
# _logger = logging.getLogger(__name__)
#
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     def action_export_to_sage(self):
#         moves = self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund") and m.state == "posted")
#         if not moves:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {"title": _("Export to Sage"),
#                            "message": _("No posted customer invoices/credit notes to export."),
#                            "type": "warning"},
#             }
#
#         exported, skipped, errs = 0, 0, []
#         for move in moves.sudo():
#             try:
#                 self.env["pastel.sync"].export_invoice(move.id)
#                 exported += 1
#             except Exception as e:
#                 skipped += 1
#                 errs.append(f"{move.display_name}: {e}")
#
#         base_msg = _("Exported: %(e)s, Skipped: %(s)s") % {"e": exported, "s": skipped}
#         msg = base_msg + (" — " + "; ".join(errs[:3]) + (" …" if len(errs) > 3 else "") if errs else "")
#         return {
#             "type": "ir.actions.client",
#             "tag": "display_notification",
#             "params": {"title": _("Export to Sage"),
#                        "message": msg,
#                        "type": "warning" if errs else "success"},
#         }
#
