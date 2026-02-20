# -*- coding: utf-8 -*-
import logging
from odoo import models, _
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    def action_export_to_sage(self):
        moves = self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund") and m.state == "posted")
        if not moves:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Export to Sage"),
                           "message": _("No posted customer invoices/credit notes to export."),
                           "type": "warning"},
            }

        exported, skipped, errs = 0, 0, []
        for move in moves.sudo():
            try:
                self.env["pastel.sync"].export_invoice(move.id)
                exported += 1
            except Exception as e:
                skipped += 1
                errs.append(f"{move.display_name}: {e}")

        base_msg = _("Exported: %(e)s, Skipped: %(s)s") % {"e": exported, "s": skipped}
        msg = base_msg + (" — " + "; ".join(errs[:3]) + (" …" if len(errs) > 3 else "") if errs else "")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Export to Sage"),
                       "message": msg,
                       "type": "warning" if errs else "success"},
        }







# # -*- coding: utf-8 -*-
# import json
# import requests
# from odoo import models, api, _
# from odoo.exceptions import UserError
# import logging
#
# _logger = logging.getLogger(__name__)
#
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     def action_export_to_sage(self):
#         moves = self.filtered(lambda m: m.move_type in ("out_invoice","out_refund") and m.state == "posted")
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


# # -*- coding: utf-8 -*-
# import json
# import requests
# from odoo import models, api, _
# from odoo.exceptions import UserError
# import logging
#
# _logger = logging.getLogger(__name__)
#
#
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     def action_export_to_sage(self):
#         """Export posted customer invoices/credit notes to Sage via a duplicate-proof upsert.
#         Uses POST /invoices/upsert only (no PUT). Idempotent by invoice_id (move.id).
#         """
#         moves = self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund") and m.state == "posted")
#         if not moves:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {
#                     "title": _("Export to Sage"),
#                     "message": _("No posted customer invoices/credit notes to export."),
#                     "type": "warning",
#                 },
#             }
#
#         # Bridge base URL + API key are provided by your pastel.sync helper
#         base, key = self.env["pastel.sync"]._conf()
#         url = f"{base.rstrip('/')}/invoices/upsert"
#
#         exported, skipped, errs = 0, 0, []
#
#         for move in moves.sudo():
#             try:
#                 # Build your existing payload (already dedupes lines)
#                 payload = self.env["pastel.sync"]._build_invoice_payload(move)
#
#                 # Use a stable external id so the bridge can upsert deterministically
#                 # Choose something immutable. move.id works well.
#                 payload["invoice_id"] = str(move.id)
#
#                 # The bridge requires customer_code to be present
#                 if not payload.get("customer_code"):
#                     raise UserError(_("Partner has no Sage code/ref for %s") % (move.partner_id.display_name,))
#
#                 headers = {
#                     "x-api-key": key,
#                     "Content-Type": "application/json",
#                     # Optional: protects against retries / duplicate submissions
#                     "Idempotency-Key": f"odoo-{move.id}-{payload['invoice_id']}-{payload.get('document_type', 3)}",
#                 }
#
#                 resp = requests.post(url, json=payload, headers=headers, timeout=40)
#                 if not (200 <= resp.status_code < 300):
#                     raise UserError(_("Bridge error %s: %s") % (resp.status_code, resp.text))
#
#                 data = {}
#                 try:
#                     data = resp.json() if resp.text else {}
#                 except Exception:
#                     pass
#
#                 # Prefer invoice_id returned by the bridge; fall back to doc_no or our payload
#                 returned_no = data.get("invoice_id") or data.get("doc_no") or payload["invoice_id"]
#                 if move.x_pastel_doc_no != returned_no:
#                     move.write({"x_pastel_doc_no": returned_no})
#
#                 _logger.info("Sage upsert OK for %s (key=%s)", move.display_name, returned_no)
#                 exported += 1
#
#             except Exception as e:
#                 skipped += 1
#                 msg = f"{move.display_name}: {e}"
#                 errs.append(msg)
#                 _logger.exception("Sage export failed: %s", msg)
#
#         # Toast summary
#         base_msg = _("Exported: %(e)s, Skipped: %(s)s") % {"e": exported, "s": skipped}
#         if errs:
#             msg = base_msg + " — " + "; ".join(errs[:3]) + (" …" if len(errs) > 3 else "")
#             typ = "warning"
#         else:
#             msg = base_msg
#             typ = "success"
#
#         # Optional log row
#         try:
#             self.env["pastel.sync"]._log("invoice", exported, 0,
#                                          notes=f"total={exported+skipped}, skipped={skipped}, errors={len(errs)}")
#         except Exception:
#             # Don't hard-fail UI if logging helper isn't available
#             pass
#
#         return {
#             "type": "ir.actions.client",
#             "tag": "display_notification",
#             "params": {"title": _("Export to Sage"), "message": msg, "type": typ},
#         }



# import json
# import time
# import requests
# from urllib.parse import quote
#
# from odoo import models, api, _
# from odoo.exceptions import UserError
# import logging
# _logger = logging.getLogger(__name__)
#
#
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#
#
#     def action_export_to_sage(self):
#         """Runs idempotent upsert per posted customer invoice/refund."""
#
#         moves = self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund") and m.state == "posted")
#         if not moves:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {"title": _("Export to Sage"),
#                            "message": _("No posted customer invoices/credit notes to export."),
#                            "type": "warning"},
#             }
#         exported, skipped, errs = 0, 0, []
#         for move in moves.sudo():
#             try:
#                 self.env["pastel.sync"].export_invoice(move.id)
#                 exported += 1
#             except Exception as e:
#                 skipped += 1
#                 errs.append(f"{move.display_name}: {e}")
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
#     # ---- small helper: ask the bridge deterministically ----
#     def _bridge_invoice_exists(self, base, key, doc_no, doc_type):
#         url = f"{base.rstrip('/')}/invoices/exists"
#         headers = {"x-api-key": key}
#         r = requests.get(url, params={"doc_no": doc_no, "doc_type": int(doc_type)}, headers=headers, timeout=15)
#         r.raise_for_status()
#         j = r.json() if r.text else {}
#         return bool(j.get("exists"))
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
#         base, key = self.env["pastel.sync"]._conf()
#         exported = 0
#         skipped = 0
#         errors = []
#
#         for move in moves.sudo():
#             try:
#                 # build payload once (also dedupes lines via your _build_invoice_payload)
#                 payload = self.env["pastel.sync"]._build_invoice_payload(move)
#                 doc_no   = payload.get("doc_no")
#                 doc_type = int(payload.get("document_type") or 3)
#                 if not doc_no:
#                     raise UserError(_("Missing doc_no for %s") % (move.display_name,))
#
#                 headers = {
#                     "x-api-key": key,
#                     "Content-Type": "application/json",
#                     "Idempotency-Key": f"odoo-{move.id}-{doc_no}-{doc_type}",  # optional protection
#                 }
#                 put_url  = f"{base.rstrip('/')}/invoices/{quote(doc_no, safe='')}"
#                 post_url = f"{base.rstrip('/')}/invoices"
#
#                 # 1) decide path:
#                 #    if we already stored a Sage number -> update;
#                 #    else ask the bridge if (doc_no, doc_type) exists.
#                 if move.x_pastel_doc_no:
#                     exists = True
#                 else:
#                     exists = self._bridge_invoice_exists(base, key, doc_no, doc_type)
#
#                 # 2) do it with race-safe fallbacks
#                 if exists:
#                     resp = requests.put(put_url, json=payload, headers=headers, timeout=30)
#                     if resp.status_code == 404:  # deleted between check and update
#                         resp = requests.post(post_url, json=payload, headers=headers, timeout=30)
#                         if resp.status_code == 409:  # created concurrently
#                             resp = requests.put(put_url, json=payload, headers=headers, timeout=30)
#                     action_word = "Updated"
#                 else:
#                     resp = requests.post(post_url, json=payload, headers=headers, timeout=30)
#                     if resp.status_code == 409:  # existed already
#                         resp = requests.put(put_url, json=payload, headers=headers, timeout=30)
#                     action_word = "Created"
#
#                 if not (200 <= resp.status_code < 300):
#                     raise UserError(_("Bridge error %s: %s") % (resp.status_code, resp.text))
#
#                 # 3) persist authoritative doc_no so future runs always UPDATE
#                 try:
#                     data = resp.json() if resp.text else {}
#                 except Exception:
#                     data = {}
#                 returned_no = data.get("doc_no") or doc_no
#                 if move.x_pastel_doc_no != returned_no:
#                     move.write({"x_pastel_doc_no": returned_no})
#
#                 _logger.info("Sage %s OK for %s (%s)", action_word, move.display_name, returned_no)
#                 exported += 1
#
#             except Exception as e:
#                 skipped += 1
#                 msg = f"{move.display_name}: {e}"
#                 errors.append(msg)
#                 _logger.exception("Sage export failed: %s", msg)
#
#         # toast
#         base_msg = _("Exported: %(e)s, Skipped: %(s)s") % {"e": exported, "s": skipped}
#         if errors:
#             msg = base_msg + " — " + "; ".join(errors[:3]) + ("" if len(errors) <= 3 else " …")
#             typ = "warning"
#         else:
#             msg = base_msg
#             typ = "success"
#
#         # optional log row
#         self.env["pastel.sync"]._log("invoice", exported, 0, notes=f"total={exported+skipped}, skipped={skipped}, errors={len(errors)}")
#
#         return {
#             "type": "ir.actions.client",
#             "tag": "display_notification",
#             "params": {"title": _("Export to Sage"), "message": msg, "type": typ},
#         }
#
#
# # from odoo import models, _
# from odoo.exceptions import UserError
#
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     # -------------------------------------------------------------------
#     # Button: Export selected posted customer invoices/credit notes
#     # -------------------------------------------------------------------
#     def action_export_to_sage(self):
#         moves = self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund") and m.state == "posted")
#         if not moves:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {
#                     "title": _("Export to Sage"),
#                     "message": _("No posted customer invoices/credit notes to export."),
#                     "type": "warning",
#                 },
#             }
#
#         try:
#             res = self.env["pastel.sync"].export_invoices_by_ids(moves.ids) or {}
#         except Exception as e:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {
#                     "title": _("Export to Sage"),
#                     "message": _("Export failed: %s") % (e,),
#                     "type": "danger",
#                     "sticky": True,
#                 },
#             }
#
#         exported = int(res.get("exported", 0))
#         skipped = int(res.get("skipped", 0))
#         errors = list(res.get("errors") or [])
#         if not errors and res.get("results"):
#             errors = [r.get("error") for r in res["results"] if not r.get("ok") and r.get("error")]
#
#         total = exported + skipped
#         self.env["pastel.sync"]._log("invoice", exported, 0,
#                                      notes=f"total={total}, skipped={skipped}, errors={len(errors)}")
#
#         base_msg = _("Exported: %(e)s, Skipped: %(s)s") % {"e": exported, "s": skipped}
#         if errors:
#             msg = base_msg + " — " + "; ".join(errors[:3]) + ("" if len(errors) <= 3 else " …")
#             notif_type = "warning"
#         else:
#             msg = base_msg
#             notif_type = "success"
#
#         return {
#             "type": "ir.actions.client",
#             "tag": "display_notification",
#             "params": {"title": _("Export to Sage"), "message": msg, "type": notif_type},
#         }

    # def action_export_to_sage(self):
    #     moves = self.filtered(lambda m: m.move_type in ("out_invoice","out_refund") and m.state == "posted")
    #     if not moves:
    #         return {
    #             "type": "ir.actions.client",
    #             "tag": "display_notification",
    #             "params": {
    #                 "title": _("Export to Sage"),
    #                 "message": _("No posted customer invoices/credit notes to export."),
    #                 "type": "warning",
    #             },
    #         }
    #
    #     try:
    #         res = self.env["pastel.sync"].export_invoices_by_ids(moves.ids) or {}
    #     except Exception as e:
    #         return {
    #             "type": "ir.actions.client",
    #             "tag": "display_notification",
    #             "params": {
    #                 "title": _("Export to Sage"),
    #                 "message": _("Export failed: %s") % (e,),
    #                 "type": "danger",
    #                 "sticky": True,
    #             },
    #         }
    #
    #     exported = int(res.get("exported", 0))
    #     skipped  = int(res.get("skipped", 0))
    #     # Prefer top-level errors; if missing, derive from results
    #     errors   = list(res.get("errors") or [])
    #     if not errors and res.get("results"):
    #         errors = [r.get("error") for r in res["results"] if not r.get("ok") and r.get("error")]
    #
    #     total = exported + skipped
    #
    #     self.env["pastel.sync"]._log(
    #         "invoice", exported, 0,
    #         notes=f"total={total}, skipped={skipped}, errors={len(errors)}"
    #     )
    #
    #     base_msg = _("Exported: %(e)s, Skipped: %(s)s") % {"e": exported, "s": skipped}
    #     if errors:
    #         msg = base_msg + " — " + "; ".join(errors[:3]) + ("" if len(errors) <= 3 else " …")
    #         notif_type = "warning"
    #     else:
    #         msg = base_msg
    #         notif_type = "success"
    #
    #     return {
    #         "type": "ir.actions.client",
    #         "tag": "display_notification",
    #         "params": {"title": _("Export to Sage"), "message": msg, "type": notif_type},
    #     }



# from odoo import models, _
# from odoo.exceptions import UserError
#
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     def action_export_to_sage(self):
#         # Only posted customer invoices / credit notes
#         moves = self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund") and m.state == "posted")
#         if not moves:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {
#                     "title": _("Export to Sage"),
#                     "message": _("No posted customer invoices/credit notes to export."),
#                     "type": "warning",
#                 },
#             }
#
#         try:
#             res = self.env["pastel.sync"].export_invoices_by_ids(moves.ids) or {}
#         except Exception as e:
#             # Hard failure talking to the connector
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {
#                     "title": _("Export to Sage"),
#                     "message": _("Export failed: %s") % (e,),
#                     "type": "danger",
#                     "sticky": True,
#                 },
#             }
#
#         # Backward/forward compatible result parsing
#         exported = int(res.get("exported", 0))
#         skipped  = int(res.get("skipped", 0))
#         errors   = list(res.get("errors", []))
#
#         # If the connector returned only per-item results, derive counts/errors
#         if not exported and not skipped and res.get("results"):
#             results = res["results"]
#             exported = sum(1 for r in results if r.get("ok"))
#             skipped  = sum(1 for r in results if not r.get("ok"))
#             # collect message strings if present
#             if not errors:
#                 errors = [r.get("error") for r in results if not r.get("ok") and r.get("error")]
#
#         total = exported + skipped
#
#         # Optional log line (won’t crash if keys missing)
#         self.env["pastel.sync"]._log(
#             "invoice",
#             exported,
#             0,
#             notes=f"total={total}, skipped={skipped}, errors={len(errors)}"
#         )
#
#         # Build user-facing message
#         base_msg = _("Exported: %(e)s, Skipped: %(s)s") % {"e": exported, "s": skipped}
#         if errors:
#             msg = base_msg + " — " + "; ".join(errors[:3]) + ("" if len(errors) <= 3 else " …")
#             notif_type = "warning"
#         else:
#             msg = base_msg
#             notif_type = "success"
#
#         return {
#             "type": "ir.actions.client",
#             "tag": "display_notification",
#             "params": {
#                 "title": _("Export to Sage"),
#                 "message": msg,
#                 "type": notif_type,
#             },
#         }
#


# from odoo import models, _
#
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     def action_export_to_sage(self):
#         # Export all selected posted customer invoices/refunds
#         moves = self.filtered(lambda m: m.move_type in ("out_invoice","out_refund") and m.state == "posted")
#         res = self.env["pastel.sync"].export_invoices_by_ids(moves.ids)
#         # Optional toast:
#         self.env["pastel.sync"]._log("invoice", res.get("exported",0), 0, notes=f"errors: {len(res.get('errors',[]))}")
#         return {
#             "type": "ir.actions.client",
#             "tag": "display_notification",
#             "params": {
#                 "title": _("Export to Sage"),
#                 "message": _("Exported: %(e)s, Skipped: %(s)s") % {"e": res["exported"], "s": res["skipped"]},
#                 "type": "success" if not res["errors"] else "warning",
#             },
#         }


# # -*- coding: utf-8 -*-
# # File: your_module/models/account_move_pastel_export.py
#
# import json
# from odoo import models, api, _
#
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     # Build Sage-friendly JSON from a customer invoice/credit note
#     def _to_pastel_invoice_payload(self):
#         self.ensure_one()
#         if self.move_type not in ("out_invoice", "out_refund"):
#             return None  # only export AR docs
#
#         # Adjust if your bridge expects different codes:
#         doc_type = 1 if self.move_type == "out_invoice" else 2
#
#         # Prefer Pastel code; fall back to ref or partner id
#         customer_code = (
#             self.partner_id.x_pastel_code
#             or self.partner_id.ref
#             or str(self.partner_id.id)
#         )
#
#         payload = {
#             "doc_no": self.x_pastel_doc_no or str(self.id),  # idempotency
#             "document_type": doc_type,
#             "invoice_date": self.invoice_date and self.invoice_date.isoformat(),
#             "customer_code": customer_code,
#             "excl_incl": 0,  # 0 = totals excl tax; 1 = incl (must match your bridge logic)
#             "lines": [],
#         }
#
#         # Lines (skip display rows)
#         for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
#             product_code = (
#                 line.product_id.product_tmpl_id.x_pastel_item_code
#                 or line.product_id.default_code
#                 or (line.product_id and str(line.product_id.id))
#             )
#
#             # Simple tax mapping: use custom field on tax if present, else pass percentage
#             tax_code = None
#             if line.tax_ids:
#                 tax = line.tax_ids[:1]
#                 tax_code = getattr(tax, "x_pastel_tax_code", False) or (
#                     str(int(tax.amount)) if float(tax.amount).is_integer() else str(tax.amount)
#                 )
#
#             payload["lines"].append({
#                 "product_code": product_code,
#                 "name": line.name or (line.product_id.display_name if line.product_id else "Line"),
#                 "quantity": float(line.quantity or 0.0),
#                 "price_unit": float(line.price_unit or 0.0),
#                 "tax_code": tax_code,
#             })
#
#         return payload
#
#     # Manual “Export to Sage” action (button)
#     def action_export_to_pastel(self):
#         Q = self.env["pastel.sync.queue"].sudo()
#         for inv in self:
#             if inv.state != "posted" or inv.move_type not in ("out_invoice", "out_refund"):
#                 # Only export posted AR docs
#                 continue
#             payload = inv._to_pastel_invoice_payload()
#             if not payload:
#                 continue
#             Q.create({
#                 "model": "account.move",
#                 "res_id": inv.id,
#                 "operation": "write" if inv.x_pastel_doc_no else "create",
#                 "payload": json.dumps(payload),
#             })
#         # Optionally push now (non-blocking; errors are logged on the queue)
#         Q.process_queue(limit=50)
#         return True
#
#     # Auto-enqueue on post
#     def action_post(self):
#         res = super().action_post()
#         Q = self.env["pastel.sync.queue"].sudo()
#         if not Q._push_enabled():
#             return res
#         for inv in self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund")):
#             payload = inv._to_pastel_invoice_payload()
#             if not payload:
#                 continue
#             Q.create({
#                 "model": "account.move",
#                 "res_id": inv.id,
#                 "operation": "create" if not inv.x_pastel_doc_no else "write",
#                 "payload": json.dumps(payload),
#             })
#         return res
