"""Payment extensions linking registrations to batch invoices."""

# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)
_logger.info("pastel_batch_payment: account_payment.py loaded")


class AccountPayment(models.Model):
    """Track batch invoice linkage and derived batch state on payments."""

    _inherit = "account.payment"

    # # Link back to the originating invoice when payment is created in Batch mode
    # batch_invoice_id = fields.Many2one(
    #     "account.move",
    #     string="Batch Invoice",
    #     help="If the payment was registered in Batch mode, store the originating invoice here."
    # )
    # batch_invoice_id = fields.Many2one(
    #     "account.move",
    #     string="Batch Invoice",
    #     domain="[('move_type', 'in', ('out_invoice', 'in_invoice')), ('state', '=', 'posted'), ('payment_state', '!=', 'paid')]",
    #     help="If the payment was registered in Batch mode, store the originating invoice here."
    # )

    batch_invoice_id = fields.Many2one(
        "account.move",
        string="Batch Invoice",
        domain=[
            ('move_type', 'in', ('out_invoice', 'in_invoice')),
            ('state', '=', 'posted'),
            ('payment_state', '!=', 'paid'),
            ('payment_state', '!=', 'partial'),
            ('has_batch_payment', '=', False),
        ]
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Mark linked invoice as having a batch payment when created."""
        payments = super().create(vals_list)

        for payment in payments:
            if payment.batch_invoice_id:
                payment.batch_invoice_id.has_batch_payment = True

        return payments

    def write(self, vals):
        """Keep has_batch_payment in sync when batch_invoice_id is set."""
        res = super().write(vals)

        for payment in self:
            if payment.batch_invoice_id:
                payment.batch_invoice_id.has_batch_payment = True

        return res
    # batch_invoice_id = fields.Many2one(
    #     "account.move",
    #     string="Batch Invoice",
    #     domain=[
    #         ('move_type', 'in', ('out_invoice', 'in_invoice')),
    #         ('state', '=', 'posted'),
    #         ('payment_state', '!=', 'paid'),
    #         ('has_batch_payment', '=', False),
    #     ]
    # )

    def action_create_payments(self):
        """Auto-link payment to active invoice in batch mode."""
        res = super().action_create_payments()

        # Only when registering payment from invoice
        if self.env.context.get("active_model") != "account.move":
            return res

        invoice = self.env["account.move"].browse(
            self.env.context.get("active_ids", [])
        ).exists()

        if not invoice:
            return res

        payments = self.payment_id

        # Fallback (Odoo 17 behavior)
        if not payments and isinstance(res, dict):
            if res.get("res_model") == "account.payment" and res.get("res_id"):
                payments = self.env["account.payment"].browse(res["res_id"]).exists()

        # if payments:
        #     payments.write({
        #         "batch_invoice_id": invoice.id
        #     })
        #     _logger.info("Batch invoice auto-set on payment(s): %s", payments.ids)

        if payments:
            payments.write({
                "batch_invoice_id": invoice.id
            })

            invoice.write({
                "has_batch_payment": True
            })

        return res

    _logger.info("BATCH REGISTER PAYMENT OVERRIDE LOADED")

    batch_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('validated', 'Validated'),
            ('exported', 'Exported'),
            ('paid', 'Paid')
        ],
        compute="_compute_batch_state",
        search="_search_batch_state",
        store=False,
    )

    # batch_payment_state = fields.Selection(
    #     [
    #         ('draft', 'Draft'),
    #         ('validated', 'Validated'),
    #         ('exported', 'Exported'),
    #         ('paid', 'Paid'),
    #     ],
    #     string="Batch Payment State",
    #     copy=False,
    #     index=True,
    # )

    batch_payment_state = fields.Selection([
        ('draft', 'Draft'),
        ('not_paid', 'Not Paid'),
        ('validated', 'Validated'),
        ('exported', 'Exported'),
        ('partial', 'Partial Paid'),
        ('paid', 'Paid'),
    ],
        default='draft',
        string="Batch Payment State",
        copy=False,
        index=True
    )

    in_exported_batch = fields.Boolean(
        string="In Exported Batch",
        compute="_compute_in_exported",
        search="_search_in_exported_batch",
        store=False,
    )

    # ---- helpers ----
    def _payment_ids_in_batch_state(self, states):
        """Return set of payment IDs that appear in any batch with state in `states`."""
        lines = self.env['batch.payment.line'].search_read(
            [('payment_id', 'in', self.ids)], ['payment_id', 'batch_id']
        )
        batch_ids = {l['batch_id'][0] for l in lines if l.get('batch_id')}
        if not batch_ids:
            return set()

        batches = self.env['batch.payment'].browse(list(batch_ids))
        wanted = {b.id for b in batches if b.state in set(states)}
        if not wanted:
            return set()

        return {
            l['payment_id'][0]
            for l in lines
            if l.get('batch_id') and l['batch_id'][0] in wanted and l.get('payment_id')
        }

    # ---- computes ----
    @api.depends('move_id')  # lightweight dependency
    def _compute_batch_state(self):
        """Derive highest-priority batch state for each payment."""
        for p in self:
            p.batch_state = False

        if not self:
            return

        lines = self.env['batch.payment.line'].search_read(
            [('payment_id', 'in', self.ids)],
            ['payment_id', 'batch_id']
        )
        by_payment = {}
        for l in lines:
            pid = l.get('payment_id') and l['payment_id'][0]
            bid = l.get('batch_id') and l['batch_id'][0]
            if pid and bid:
                by_payment.setdefault(pid, set()).add(bid)

        batches = self.env['batch.payment'].browse({bid for bids in by_payment.values() for bid in bids})
        state_map = {b.id: b.state for b in batches}

        for p in self:
            bids = by_payment.get(p.id) or set()
            ordered = ['exported', 'validated', 'draft', 'paid']
            for s in ordered:
                if any(state_map.get(bid) == s for bid in bids):
                    p.batch_state = s
                    break

    @api.depends('batch_state')
    def _compute_in_exported(self):
        """True when payment appears in an exported batch."""
        for p in self:
            p.in_exported_batch = (p.batch_state == 'exported')

    # ---- searches ----
    def _search_in_exported_batch(self, operator, value):
        """Domain search helper for in_exported_batch field."""
        want_true = None
        if operator in ('=', '=='):
            want_true = bool(value)
        elif operator == '!=':
            want_true = not bool(value)
        else:
            want_true = bool(value)

        BatchLine = self.env['batch.payment.line']
        exported_lines = BatchLine.search_read([], ['payment_id', 'batch_id'])
        batch_ids = {l['batch_id'][0] for l in exported_lines if l.get('batch_id')}
        batches = self.env['batch.payment'].browse(list(batch_ids))
        exported_batch_ids = {b.id for b in batches if b.state == 'exported'}
        exported_payment_ids = {
            l['payment_id'][0] for l in exported_lines
            if l.get('payment_id') and l.get('batch_id') and l['batch_id'][0] in exported_batch_ids
        }

        if want_true:
            return [('id', 'in', list(exported_payment_ids) or [0])]
        return [('id', 'not in', list(exported_payment_ids) or [0])]

    def _search_batch_state(self, operator, value):
        """Domain search helper for batch_state field."""
        if operator in ('=', '==', 'ilike', 'like'):
            wanted = {str(value)} if value else set()
        elif operator in ('in',):
            wanted = set(value or [])
        elif operator in ('!=', 'not in'):
            wanted = {'draft', 'validated', 'exported'} - set(value if isinstance(value, (list, tuple, set)) else {value})
        else:
            wanted = {str(value)} if value else set()

        if not wanted:
            return [('id', 'in', [])]

        BatchLine = self.env['batch.payment.line']
        lines = BatchLine.search_read([], ['payment_id', 'batch_id'])
        batch_ids = {l['batch_id'][0] for l in lines if l.get('batch_id')}
        batches = self.env['batch.payment'].browse(list(batch_ids))
        wanted_batch_ids = {b.id for b in batches if b.state in wanted}
        payment_ids = {
            l['payment_id'][0] for l in lines
            if l.get('payment_id') and l.get('batch_id') and l['batch_id'][0] in wanted_batch_ids
        }

        if operator in ('!=', 'not in'):
            return [('id', 'not in', list(payment_ids) or [0])]
        return [('id', 'in', list(payment_ids) or [0])]



