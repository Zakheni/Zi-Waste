# pastel_batch_payment/models/account_payment.py
import logging
_logger = logging.getLogger(__name__)
_logger.info("pastel_batch_payment: account_payment.py loaded")

from odoo import api, fields, models

class AccountPayment(models.Model):
    _inherit = "account.payment"

    batch_state = fields.Selection(
        selection=[('draft', 'Draft'), ('validated', 'Validated'), ('exported', 'Exported')],
        string="Batch State",
        compute="_compute_batch_state",
        search="_search_batch_state",
        store=False,
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

        # payments whose line.batch_id is in wanted
        return {
            l['payment_id'][0]
            for l in lines
            if l.get('batch_id') and l['batch_id'][0] in wanted and l.get('payment_id')
        }

    # ---- computes ----
    @api.depends('move_id')  # lightweight dependency; we resolve via lines anyway
    def _compute_batch_state(self):
        for p in self:
            # default None / False means "not in any batch"
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
            # If multiple lines/batches exist, prefer a “strongest” state
            # exported > validated > draft
            ordered = ['exported', 'validated', 'draft']
            for s in ordered:
                if any(state_map.get(bid) == s for bid in bids):
                    p.batch_state = s
                    break

    @api.depends('batch_state')
    def _compute_in_exported(self):
        for p in self:
            p.in_exported_batch = (p.batch_state == 'exported')

    # ---- searches ----
    def _search_in_exported_batch(self, operator, value):
        """Support domains like ('in_exported_batch', '=', True/False)."""
        # Normalize operator to '=' or '!=' behaviour for booleans
        want_true = None
        if operator in ('=', '=='):
            want_true = bool(value)
        elif operator == '!=':
            want_true = not bool(value)
        else:
            # Fallback: treat any other operator as '='
            want_true = bool(value)

        # Build on all payments (domain is applied on current search, not only self)
        # We must return a domain, not compute on `self`. So we need to compute set globally.
        # Compute exported payment ids:
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
        else:
            return [('id', 'not in', list(exported_payment_ids) or [0])]

    def _search_batch_state(self, operator, value):
        """Support domains like ('batch_state', '=', 'validated')."""
        # Normalize value to a set of wanted states
        if operator in ('=', '==', 'ilike', 'like'):
            wanted = {str(value)} if value else set()
        elif operator in ('in',):
            wanted = set(value or [])
        elif operator in ('!=', 'not in'):
            wanted = {'draft', 'validated', 'exported'} - set(value if isinstance(value, (list, tuple, set)) else {value})
        else:
            # default fall-back: behave like '='
            wanted = {str(value)} if value else set()

        if not wanted:
            return [('id', 'in', [])]  # nothing matches

        # Return payments whose batch has any of the wanted states
        BatchLine = self.env['batch.payment.line']
        lines = BatchLine.search_read([], ['payment_id', 'batch_id'])
        batch_ids = {l['batch_id'][0] for l in lines if l.get('batch_id')}
        batches = self.env['batch.payment'].browse(list(batch_ids))
        wanted_batch_ids = {b.id for b in batches if b.state in wanted}
        payment_ids = {
            l['payment_id'][0] for l in lines
            if l.get('payment_id') and l.get('batch_id') and l['batch_id'][0] in wanted_batch_ids
        }

        # Map the operator to inclusion or exclusion
        if operator in ('!=', 'not in'):
            return [('id', 'not in', list(payment_ids) or [0])]
        else:
            return [('id', 'in', list(payment_ids) or [0])]



# from odoo import api, fields, models
#
# class AccountPayment(models.Model):
#     _inherit = "account.payment"
#
#     # state-like badge we compute from related batch lines (if you added that link)
#     batch_state = fields.Selection(
#         selection=[('draft', 'Draft'), ('validated', 'Validated'), ('exported', 'Exported')],
#         string="Batch State",
#         compute="_compute_batch_state",
#         store=False
#     )
#     # helper used to hide exported ones
#     in_exported_batch = fields.Boolean(string="In Exported Batch", compute="_compute_in_exported", store=False)
#
#     @api.depends('move_id')  # adjust deps to your relation to batch lines
#     def _compute_batch_state(self):
#         for p in self:
#             # TODO: replace with your actual lookup linking payment -> batch.line -> batch
#             batch = self.env['batch.payment'].search([('line_ids.payment_id', '=', p.id)], limit=1)
#             p.batch_state = batch.state if batch else False
#
#     @api.depends('batch_state')
#     def _compute_in_exported(self):
#         for p in self:
#             p.in_exported_batch = (p.batch_state == 'exported')

    # batch_line_ids = fields.One2many(
    #     "batch.payment.line", "payment_id", string="Batch Lines", readonly=True
    # )

    # # use a string sentinel (e.g., 'none') instead of False
    # batch_state = fields.Selection(
    #     [
    #         ("none", "—"),
    #         ("draft", "Draft"),
    #         ("validated", "Validated"),
    #         ("exported", "Exported"),
    #     ],
    #     string="Batch Status",
    #     compute="_compute_batch_flags",
    #     store=True,
    # )
    #
    # in_exported_batch = fields.Boolean(
    #     string="In Exported Batch",
    #     compute="_compute_batch_flags",
    #     store=True,
    #     help="True when this payment appears in any batch with state = Exported.",
    # )
    #
    # @api.depends("batch_line_ids.batch_id.state")
    # def _compute_batch_flags(self):
    #     for pay in self:
    #         states = {bl.batch_id.state for bl in pay.batch_line_ids if bl.batch_id}
    #         if "exported" in states:
    #             pay.batch_state = "exported"
    #             pay.in_exported_batch = True
    #         elif "validated" in states:
    #             pay.batch_state = "validated"
    #             pay.in_exported_batch = False
    #         elif "draft" in states:
    #             pay.batch_state = "draft"
    #             pay.in_exported_batch = False
    #         else:
    #             pay.batch_state = "none"
    #             pay.in_exported_batch = False
    #
    #
