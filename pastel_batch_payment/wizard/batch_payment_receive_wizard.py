from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class BatchPaymentReceiveWizard(models.TransientModel):
    _name = "batch.payment.receive.wizard"
    _description = "Receive Batch Payment"

    batch_id = fields.Many2one(
        "batch.payment",
        required=True
    )

    currency_id = fields.Many2one(
        related="batch_id.currency_id"
    )

    # amount_due = fields.Monetary(
    #     related="batch_id.amount_due"
    # )

    amount_due = fields.Monetary(
        compute="_compute_amount_due",
        currency_field="currency_id",
    )

    @api.depends(
        "batch_id.amount_due",
        "batch_id.amount_due_after_credit"
    )
    def _compute_amount_due(self):
        for rec in self:
            rec.amount_due = (
                    rec.batch_id.amount_due_after_credit
                    or rec.batch_id.amount_due
            )

    amount_received = fields.Monetary(
        string="Amount Received",
        required=True,
        currency_field="currency_id",
    )

    difference = fields.Monetary(
        string="Difference",
        compute="_compute_difference",
        currency_field="currency_id",
    )

    payment_date = fields.Date(
        required=True,
        default=fields.Date.today
    )

    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain="[('type','in',['bank','cash'])]"
    )

    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Payment Method"
    )

    notes = fields.Text()

    @api.depends("amount_due", "amount_received")
    def _compute_difference(self):
        for rec in self:
            rec.difference = rec.amount_due - rec.amount_received




    # def action_receive_payment(self):
    #
    #     self.ensure_one()
    #
    #     batch = self.batch_id
    #
    #     batch.amount_received = self.amount_received
    #     batch.payment_difference = self.difference
    #     batch.payment_date = self.payment_date
    #
    #     overpayment = max(
    #         (self.amount_received or 0.0) - (self.amount_due or 0.0),
    #         0.0
    #     )
    #
    #     # ---------------------------------------------------
    #     # FULL PAYMENT
    #     # ---------------------------------------------------
    #     if self.amount_received >= self.amount_due:
    #
    #         batch.state = "paid"
    #
    #
    #         for line in batch.line_ids:
    #
    #             invoice = line.move_id
    #             payment = line.payment_id
    #
    #             if not invoice:
    #                 continue
    #
    #             invoice.write({
    #                 "batch_payment_state": "paid",
    #                 "amount_paid_batch": line.amount,
    #                 "amount_outstanding_batch": 0.0,
    #             })
    #
    #             # -------------------------------------
    #             # Native Odoo Reconciliation
    #             # -------------------------------------
    #             if (
    #                     payment
    #                     and invoice.state == "posted"
    #                     and payment.state == "posted"
    #             ):
    #
    #                 inv_lines = invoice.line_ids.filtered(
    #                     lambda l:
    #                     l.account_id.account_type in (
    #                         "asset_receivable",
    #                         "liability_payable"
    #                     )
    #                     and not l.reconciled
    #                 )
    #
    #                 pay_lines = payment.move_id.line_ids.filtered(
    #                     lambda l:
    #                     l.account_id in inv_lines.mapped("account_id")
    #                     and not l.reconciled
    #                 )
    #
    #                 if inv_lines and pay_lines:
    #
    #                     try:
    #
    #                         (inv_lines + pay_lines).reconcile()
    #
    #                         _logger.warning(
    #                             "FULL RECONCILIATION SUCCESSFUL: %s",
    #                             invoice.name
    #                         )
    #
    #                     except Exception as e:
    #
    #                         _logger.warning(
    #                             "FULL RECONCILIATION FAILED: %s",
    #                             str(e)
    #                         )
    #         # Update payments
    #         batch.line_ids.mapped("payment_id").write({
    #             "batch_payment_state": "paid"
    #         })
    #
    #         # ---------------------------------------------------
    #         # CUSTOMER CREDIT
    #         # ---------------------------------------------------
    #         if overpayment > 0:
    #
    #             first_invoice = batch.line_ids[:1]
    #
    #             partner = (
    #                 first_invoice.move_id.partner_id
    #                 if first_invoice and first_invoice.move_id
    #                 else False
    #             )
    #
    #             if partner:
    #
    #                 # -------------------------------------
    #                 # Prevent duplicate credits per batch
    #                 # -------------------------------------
    #                 existing_credit = self.env["customer.credit"].search([
    #                     ("batch_id", "=", batch.id)
    #                 ], limit=1)
    #
    #                 if not existing_credit:
    #
    #                     self.env["customer.credit"].sudo().create({
    #                         "partner_id": partner.id,
    #                         "batch_id": batch.id,
    #                         "amount": overpayment,
    #                         "balance": overpayment,
    #                         "state": "open",
    #                         "notes": _(
    #                             "Credit created from overpayment on batch %s"
    #                         ) % batch.name,
    #                     })
    #
    #                     batch.message_post(
    #                         body=_(
    #                             "Customer credit created: %s"
    #                         ) % overpayment
    #                     )
    #
    #                 else:
    #
    #                     batch.message_post(
    #                         body=_(
    #                             "Credit already exists for this batch. "
    #                             "Duplicate credit creation skipped."
    #                         )
    #                     )
    #
    #     # ---------------------------------------------------
    #     # PARTIAL PAYMENT (FIFO)
    #     # ---------------------------------------------------
    #     else:
    #
    #         batch.state = "partial"
    #
    #         remaining_amount = self.amount_received or 0.0
    #
    #         # Reset existing allocations
    #         for line in batch.line_ids:
    #
    #             invoice = line.move_id
    #
    #             if invoice:
    #                 invoice.write({
    #                     "amount_paid_batch": 0.0,
    #                     "amount_outstanding_batch": 0.0,
    #                 })
    #
    #         # FIFO allocation
    #         for line in batch.line_ids.sorted(
    #                 key=lambda l: (
    #                         l.move_id.invoice_date or fields.Date.today(),
    #                         l.move_id.id
    #                 )
    #         ):
    #
    #             invoice = line.move_id
    #
    #             if not invoice:
    #                 continue
    #
    #             invoice_amount = line.amount or 0.0
    #
    #             # No money left
    #             if remaining_amount <= 0:
    #                 invoice.write({
    #                     "batch_payment_state": "not_paid",
    #                     "amount_paid_batch": 0.0,
    #                     "amount_outstanding_batch": invoice_amount,
    #                 })
    #
    #                 continue
    #
    #             allocated_amount = min(
    #                 remaining_amount,
    #                 invoice_amount
    #             )
    #
    #             outstanding_amount = (
    #                     invoice_amount - allocated_amount
    #             )
    #
    #             if outstanding_amount <= 0:
    #
    #                 state = "paid"
    #
    #             elif allocated_amount > 0:
    #
    #                 state = "partial"
    #
    #             else:
    #
    #                 state = "not_paid"
    #
    #             # invoice.write({
    #             #     "batch_payment_state": state,
    #             #     "amount_paid_batch": allocated_amount,
    #             #     "amount_outstanding_batch": outstanding_amount,
    #             # })
    #
    #             payment = line.payment_id
    #
    #             # -------------------------------------
    #             # Native Odoo Partial Reconciliation
    #             # -------------------------------------
    #             if (
    #                     payment
    #                     and allocated_amount > 0
    #                     and invoice.state == "posted"
    #                     and payment.state == "posted"
    #             ):
    #
    #                 inv_lines = invoice.line_ids.filtered(
    #                     lambda l:
    #                     l.account_id.account_type in (
    #                         "asset_receivable",
    #                         "liability_payable"
    #                     )
    #                     and not l.reconciled
    #                 )
    #
    #                 pay_lines = payment.move_id.line_ids.filtered(
    #                     lambda l:
    #                     l.account_id in inv_lines.mapped("account_id")
    #                     and not l.reconciled
    #                 )
    #
    #                 if inv_lines and pay_lines:
    #
    #                     try:
    #
    #                         (inv_lines + pay_lines).reconcile()
    #
    #                         _logger.warning(
    #                             "PARTIAL RECONCILIATION SUCCESSFUL: %s",
    #                             invoice.name
    #                         )
    #
    #                     except Exception as e:
    #
    #                         _logger.warning(
    #                             "PARTIAL RECONCILIATION FAILED: %s",
    #                             str(e)
    #                         )
    #
    #             remaining_amount -= allocated_amount
    #
    #         # Update payments
    #         batch.line_ids.mapped("payment_id").write({
    #             "batch_payment_state": "partial"
    #         })
    #
    #     # ---------------------------------------------------
    #     # AUDIT TRAIL
    #     # ---------------------------------------------------
    #     batch.message_post(
    #         body=_(
    #             "Payment received.<br/>"
    #             "Amount Due: %s<br/>"
    #             "Amount Received: %s<br/>"
    #             "Difference: %s"
    #         ) % (
    #                  batch.amount_due,
    #                  self.amount_received,
    #                  self.difference
    #              )
    #     )
    #
    #     return {
    #         "type": "ir.actions.client",
    #         "tag": "reload"
    #     }

    def action_receive_payment(self):

        self.ensure_one()

        batch = self.batch_id

        batch.amount_received = self.amount_received
        batch.payment_difference = self.difference
        batch.payment_date = self.payment_date

        overpayment = max(
            (self.amount_received or 0.0) - (self.amount_due or 0.0),
            0.0
        )

        # --------------------------------------------------
        # VALIDATION
        # --------------------------------------------------

        if float_is_zero(
                self.amount_received,
                precision_rounding=self.currency_id.rounding
        ):
            raise ValidationError(_(
                "Amount Received must be greater than zero."
            ))

        if float_compare(
                self.amount_received,
                0.0,
                precision_rounding=self.currency_id.rounding
        ) < 0:
            raise ValidationError(_(
                "Amount Received cannot be negative."
            ))

        # if float_compare(
        #         self.amount_received,
        #         self.amount_due,
        #         precision_rounding=self.currency_id.rounding
        # ) < 0:
        #     raise ValidationError(_(
        #         "Amount Received cannot be less than the outstanding amount."
        #     ))

        # =====================================================
        # FULL PAYMENT
        # =====================================================
        if self.amount_received >= self.amount_due:

            batch.state = "paid"

            for line in batch.line_ids:

                invoice = line.move_id
                payment = line.payment_id

                if not invoice:
                    continue

                invoice.write({
                    "batch_payment_state": "paid",
                    "amount_paid_batch": line.amount,
                    "amount_outstanding_batch": 0.0,
                })

                # -----------------------------------------
                # ODOO RECONCILIATION
                # -----------------------------------------
                if (
                        payment
                        and invoice.state == "posted"
                        and payment.state == "posted"
                ):

                    inv_lines = invoice.line_ids.filtered(
                        lambda l:
                        l.account_id.account_type in (
                            "asset_receivable",
                            "liability_payable"
                        )
                        and not l.reconciled
                    )

                    pay_lines = payment.move_id.line_ids.filtered(
                        lambda l:
                        l.account_id.account_type in (
                            "asset_receivable",
                            "liability_payable"
                        )
                        and not l.reconciled
                    )

                    _logger.warning(
                        "RECONCILING INVOICE=%s PAYMENT=%s INV=%s PAY=%s",
                        invoice.name,
                        payment.name,
                        inv_lines.ids,
                        pay_lines.ids,
                    )

                    if inv_lines and pay_lines:
                        try:

                            (inv_lines + pay_lines).reconcile()

                            _logger.warning(
                                "FULL RECONCILIATION COMPLETE: %s",
                                invoice.name
                            )

                        except Exception as e:

                            _logger.exception(
                                "FULL RECONCILIATION FAILED: %s",
                                str(e)
                            )

            batch.line_ids.mapped("payment_id").write({
                "batch_payment_state": "paid"
            })

            # -----------------------------------------
            # CUSTOMER CREDIT
            # -----------------------------------------
            if overpayment > 0:

                first_invoice = batch.line_ids[:1]

                partner = (
                    first_invoice.move_id.partner_id
                    if first_invoice and first_invoice.move_id
                    else False
                )

                if partner:

                    existing_credit = self.env["customer.credit"].search([
                        ("batch_id", "=", batch.id)
                    ], limit=1)

                    if not existing_credit:

                        self.env["customer.credit"].sudo().create({
                            "partner_id": partner.id,
                            "batch_id": batch.id,
                            "amount": overpayment,
                            "balance": overpayment,
                            "state": "open",
                            "notes": _(
                                "Credit created from overpayment on batch %s"
                            ) % batch.name,
                        })

                        batch.message_post(
                            body=_(
                                "Customer credit created: %s"
                            ) % overpayment
                        )

                    else:

                        batch.message_post(
                            body=_(
                                "Credit already exists for this batch. "
                                "Duplicate credit creation skipped."
                            )
                        )

        # =====================================================
        # PARTIAL PAYMENT (FIFO)
        # =====================================================

        else:

            batch.state = "partial"

            remaining_amount = self.amount_received or 0.0

            # Reset batch values first
            for line in batch.line_ids:

                invoice = line.move_id

                if invoice:
                    invoice.write({
                        "amount_paid_batch": 0.0,
                        "amount_outstanding_batch": 0.0,
                        "batch_payment_state": "not_paid",
                    })

            # # FIFO
            # for line in batch.line_ids.sorted(
            #         key=lambda l: (
            #                 l.move_id.invoice_date or fields.Date.today(),
            #                 l.move_id.id
            #         )
            # ):
            #
            #     invoice = line.move_id
            #     payment = line.payment_id
            #
            #     if not invoice:
            #         continue
            #
            #     invoice_amount = line.amount or 0.0
            #
            #     if remaining_amount <= 0:
            #
            #         invoice.write({
            #             "batch_payment_state": "not_paid",
            #             "amount_paid_batch": 0.0,
            #             "amount_outstanding_batch": invoice_amount,
            #         })
            #
            #         if payment:
            #             payment.batch_payment_state = "not_paid"
            #
            #         continue
            #
            #     allocated_amount = min(
            #         remaining_amount,
            #         invoice_amount
            #     )
            #
            #     outstanding_amount = (
            #             invoice_amount - allocated_amount
            #     )
            #
            #     if outstanding_amount <= 0:
            #         state = "paid"
            #     elif allocated_amount > 0:
            #         state = "partial"
            #     else:
            #         state = "not_paid"
            #
            #     invoice.write({
            #         "batch_payment_state": state,
            #         "amount_paid_batch": allocated_amount,
            #         "amount_outstanding_batch": outstanding_amount,
            #     })
            #
            #     if payment:
            #         payment.batch_payment_state = state
            #
            #     _logger.warning(
            #         "FIFO UPDATE -> %s | STATE=%s | PAID=%s | OUTSTANDING=%s",
            #         invoice.name,
            #         state,
            #         allocated_amount,
            #         outstanding_amount,
            #     )
            #
            #     # --------------------------------------------------
            #     # RECONCILE ONLY FULLY PAID INVOICES
            #     # --------------------------------------------------
            #     if (
            #             payment
            #             and outstanding_amount <= 0
            #             and invoice.state == "posted"
            #             and payment.state == "posted"
            #     ):
            #
            #         inv_lines = invoice.line_ids.filtered(
            #             lambda l:
            #             l.account_id.account_type in (
            #                 "asset_receivable",
            #                 "liability_payable"
            #             )
            #             and not l.reconciled
            #         )
            #
            #         pay_lines = payment.move_id.line_ids.filtered(
            #             lambda l:
            #             l.account_id.account_type in (
            #                 "asset_receivable",
            #                 "liability_payable"
            #             )
            #             and not l.reconciled
            #         )
            #
            #         if inv_lines and pay_lines:
            #             try:
            #
            #                 (inv_lines + pay_lines).reconcile()
            #
            #                 _logger.warning(
            #                     "FULL RECONCILIATION COMPLETE: %s",
            #                     invoice.name
            #                 )
            #
            #             except Exception as e:
            #
            #                 _logger.exception(
            #                     "RECONCILIATION FAILED: %s",
            #                     str(e)
            #                 )
            #
            #     remaining_amount -= allocated_amount
            #
            # affected_batches = self.env['batch.payment']
            #
            # for line in batch.line_ids:
            #     if line.source_batch_id:
            #         affected_batches |= line.source_batch_id
            #
            # for old_batch in affected_batches:
            #
            #     invoices = old_batch.line_ids.mapped(
            #         'payment_id.batch_invoice_id'
            #     ).filtered(lambda i: i)
            #
            #     if invoices and all(
            #             inv.batch_payment_state == 'paid'
            #             for inv in invoices
            #     ):
            #         old_batch.write({
            #             'state': 'paid'
            #         })
            #
            #         old_batch.line_ids.mapped('payment_id').write({
            #             'batch_payment_state': 'paid'
            #         })
            #
            # # Final payment states
            # for line in batch.line_ids:
            #     if line.payment_id and line.move_id:
            #         line.payment_id.batch_payment_state = (
            #             line.move_id.batch_payment_state
            #         )
            #
            # # Final batch state
            # if remaining_amount <= 0:
            #     batch.state = "partial"

            # =====================================================
            # FIFO
            # =====================================================

            for line in batch.line_ids.sorted(
                    key=lambda l: (
                            l.move_id.invoice_date or fields.Date.today(),
                            l.move_id.id
                    )
            ):

                invoice = line.move_id
                payment = line.payment_id

                if not invoice:
                    continue

                invoice_amount = line.amount or 0.0

                # -----------------------------------------
                # No funds remaining
                # -----------------------------------------
                if remaining_amount <= 0:

                    invoice.write({
                        "batch_payment_state": "not_paid",
                        "amount_paid_batch": 0.0,
                        "amount_outstanding_batch": invoice_amount,
                    })

                    if payment:
                        payment.batch_payment_state = "not_paid"

                    continue

                allocated_amount = min(
                    remaining_amount,
                    invoice_amount
                )

                outstanding_amount = (
                        invoice_amount - allocated_amount
                )

                if outstanding_amount <= 0:
                    state = "paid"
                elif allocated_amount > 0:
                    state = "partial"
                else:
                    state = "not_paid"

                invoice.write({
                    "batch_payment_state": state,
                    "amount_paid_batch": allocated_amount,
                    "amount_outstanding_batch": outstanding_amount,
                })

                if payment:
                    payment.batch_payment_state = state

                _logger.warning(
                    "FIFO UPDATE -> %s | STATE=%s | PAID=%s | OUTSTANDING=%s",
                    invoice.name,
                    state,
                    allocated_amount,
                    outstanding_amount,
                )

                # --------------------------------------------------
                # RECONCILE ONLY FULLY PAID INVOICES
                # --------------------------------------------------
                if (
                        payment
                        and outstanding_amount <= 0
                        and invoice.state == "posted"
                        and payment.state == "posted"
                ):

                    inv_lines = invoice.line_ids.filtered(
                        lambda l:
                        l.account_id.account_type in (
                            "asset_receivable",
                            "liability_payable"
                        )
                        and not l.reconciled
                    )

                    pay_lines = payment.move_id.line_ids.filtered(
                        lambda l:
                        l.account_id.account_type in (
                            "asset_receivable",
                            "liability_payable"
                        )
                        and not l.reconciled
                    )

                    if inv_lines and pay_lines:
                        try:

                            (inv_lines + pay_lines).reconcile()

                            _logger.warning(
                                "FULL RECONCILIATION COMPLETE: %s",
                                invoice.name
                            )

                        except Exception as e:

                            _logger.exception(
                                "RECONCILIATION FAILED: %s",
                                str(e)
                            )

                remaining_amount -= allocated_amount

            # =====================================================
            # KEEP PAYMENT STATES IN SYNC
            # =====================================================

            for line in batch.line_ids:

                if line.payment_id and line.move_id:
                    line.payment_id.batch_payment_state = (
                        line.move_id.batch_payment_state
                    )

            # =====================================================
            # UPDATE CURRENT BATCH STATUS
            # =====================================================

            # current_invoices = batch.line_ids.mapped(
            #     "move_id"
            # ).filtered(lambda i: i)
            #
            # if current_invoices:
            #
            #     if all(
            #             inv.batch_payment_state == "paid"
            #             for inv in current_invoices
            #     ):
            #
            #         batch.state = "paid"
            #
            #         batch.line_ids.mapped(
            #             "payment_id"
            #         ).write({
            #             "batch_payment_state": "paid"
            #         })
            #
            #     else:
            #
            #         batch.state = "partial"
            #
            #         batch.line_ids.mapped(
            #             "payment_id"
            #         ).write({
            #             "batch_payment_state": "partial"
            #         })

            # =====================================================
            # UPDATE CURRENT BATCH STATUS
            # =====================================================

            current_invoices = batch.line_ids.mapped(
                "move_id"
            ).filtered(lambda i: i)

            if current_invoices:

                all_paid = all(
                    inv.amount_outstanding_batch <= 0
                    for inv in current_invoices
                )

                if all_paid:

                    batch.write({
                        "state": "paid"
                    })

                    batch.line_ids.mapped(
                        "payment_id"
                    ).write({
                        "batch_payment_state": "paid"
                    })

                    _logger.warning(
                        "BATCH %s CLOSED AS PAID",
                        batch.name
                    )

                else:

                    batch.write({
                        "state": "partial"
                    })

                    for line in batch.line_ids:

                        if not line.move_id or not line.payment_id:
                            continue

                        line.payment_id.batch_payment_state = (
                            line.move_id.batch_payment_state
                        )

                    _logger.warning(
                        "BATCH %s REMAINS PARTIAL",
                        batch.name
                    )

            # # =====================================================
            # # AUTO CLOSE PREVIOUS PARTIAL BATCHES
            # # =====================================================
            #
            # affected_batches = self.env["batch.payment"]
            #
            # for line in batch.line_ids:
            #
            #     if not line.move_id:
            #         continue
            #
            #     old_lines = self.env[
            #         "batch.payment.line"
            #     ].search([
            #         ("move_id", "=", line.move_id.id),
            #         ("batch_id", "!=", batch.id),
            #     ])
            #
            #     affected_batches |= old_lines.mapped(
            #         "batch_id"
            #     )
            #
            # for old_batch in affected_batches:
            #
            #     invoices = old_batch.line_ids.mapped(
            #         "move_id"
            #     ).filtered(lambda i: i)
            #
            #     if not invoices:
            #         continue
            #
            #     if all(
            #             inv.batch_payment_state == "paid"
            #             for inv in invoices
            #     ):
            #         old_batch.write({
            #             "state": "paid"
            #         })
            #
            #         old_batch.line_ids.mapped(
            #             "payment_id"
            #         ).write({
            #             "batch_payment_state": "paid"
            #         })
            #
            #         _logger.warning(
            #             "OLD BATCH AUTO CLOSED -> %s",
            #             old_batch.name
            #         )

            # =====================================================
            # RECALCULATE CURRENT + PREVIOUS BATCHES
            # =====================================================

            affected_batches = batch

            for line in batch.line_ids:

                if not line.move_id:
                    continue

                old_lines = self.env[
                    "batch.payment.line"
                ].search([
                    ("move_id", "=", line.move_id.id),
                ])

                affected_batches |= old_lines.mapped(
                    "batch_id"
                )

            _logger.warning(
                "AFFECTED BATCHES -> %s",
                affected_batches.mapped("name")
            )

            affected_batches._recompute_batch_state()

            # =====================================================
            # CLOSE PREVIOUS PARTIAL BATCHES
            # =====================================================

            # =====================================================
            # AUTO CLOSE PREVIOUS PARTIAL BATCHES
            # =====================================================

            source_batches = batch.line_ids.mapped(
                "source_batch_id"
            ).filtered(
                lambda b: b and b.state == "partial"
            )

            for old_batch in source_batches:

                old_invoices = old_batch.line_ids.mapped(
                    "move_id"
                ).filtered(lambda i: i)

                if not old_invoices:
                    continue

                _logger.warning(
                    "CHECKING OLD BATCH %s",
                    old_batch.name
                )

                for inv in old_invoices:
                    _logger.warning(
                        "   %s | OUT=%s | STATE=%s",
                        inv.name,
                        inv.amount_outstanding_batch,
                        inv.batch_payment_state,
                    )

                all_paid = all(
                    inv.amount_outstanding_batch <= 0
                    for inv in old_invoices
                )

                if all_paid:

                    old_batch.write({
                        "state": "paid"
                    })

                    old_batch.line_ids.mapped(
                        "payment_id"
                    ).write({
                        "batch_payment_state": "paid"
                    })

                    _logger.warning(
                        "OLD BATCH CLOSED -> %s",
                        old_batch.name
                    )

                else:

                    _logger.warning(
                        "OLD BATCH STILL PARTIAL -> %s",
                        old_batch.name
                    )

            # source_batches = batch.line_ids.mapped(
            #     "source_batch_id"
            # ).filtered(
            #     lambda b: b and b.state == "partial"
            # )
            #
            # for old_batch in source_batches:
            #
            #     old_invoices = old_batch.line_ids.mapped(
            #         "move_id"
            #     ).filtered(lambda i: i)
            #
            #     if not old_invoices:
            #         continue
            #
            #     all_paid = all(
            #         inv.batch_payment_state == "paid"
            #         for inv in old_invoices
            #     )
            #
            #     _logger.warning(
            #         "CHECKING OLD BATCH %s -> ALL PAID=%s",
            #         old_batch.name,
            #         all_paid
            #     )
            #
            #     if all_paid:
            #         old_batch.write({
            #             "state": "paid"
            #         })
            #
            #         old_batch.line_ids.mapped(
            #             "payment_id"
            #         ).write({
            #             "batch_payment_state": "paid"
            #         })
            #
            #         _logger.warning(
            #             "OLD BATCH CLOSED -> %s",
            #             old_batch.name
            #         )


        # else:
        #
        #     batch.state = "partial"
        #
        #     remaining_amount = self.amount_received or 0.0
        #
        #     for line in batch.line_ids:
        #
        #         invoice = line.move_id
        #
        #         if invoice:
        #             invoice.write({
        #                 "amount_paid_batch": 0.0,
        #                 "amount_outstanding_batch": 0.0,
        #             })
        #
        #     for line in batch.line_ids.sorted(
        #             key=lambda l: (
        #                     l.move_id.invoice_date or fields.Date.today(),
        #                     l.move_id.id
        #             )
        #     ):
        #
        #         invoice = line.move_id
        #         payment = line.payment_id
        #
        #         if not invoice:
        #             continue
        #
        #         invoice_amount = line.amount or 0.0
        #
        #         if remaining_amount <= 0:
        #             invoice.write({
        #                 "batch_payment_state": "not_paid",
        #                 "amount_paid_batch": 0.0,
        #                 "amount_outstanding_batch": invoice_amount,
        #             })
        #
        #             continue
        #
        #         allocated_amount = min(
        #             remaining_amount,
        #             invoice_amount
        #         )
        #
        #         outstanding_amount = (
        #                 invoice_amount - allocated_amount
        #         )
        #
        #         if outstanding_amount <= 0:
        #             state = "paid"
        #         elif allocated_amount > 0:
        #             state = "partial"
        #         else:
        #             state = "not_paid"
        #
        #         # RESTORED
        #         invoice.write({
        #             "batch_payment_state": state,
        #             "amount_paid_batch": allocated_amount,
        #             "amount_outstanding_batch": outstanding_amount,
        #         })
        #
        #         _logger.warning(
        #             "FIFO UPDATE -> %s | STATE=%s | PAID=%s | OUTSTANDING=%s",
        #             invoice.name,
        #             state,
        #             allocated_amount,
        #             outstanding_amount,
        #         )
        #
        #         # -----------------------------------------
        #         # ODOO RECONCILIATION
        #         # -----------------------------------------
        #         if (
        #                 payment
        #                 and allocated_amount > 0
        #                 and invoice.state == "posted"
        #                 and payment.state == "posted"
        #         ):
        #
        #             inv_lines = invoice.line_ids.filtered(
        #                 lambda l:
        #                 l.account_id.account_type in (
        #                     "asset_receivable",
        #                     "liability_payable"
        #                 )
        #                 and not l.reconciled
        #             )
        #
        #             pay_lines = payment.move_id.line_ids.filtered(
        #                 lambda l:
        #                 l.account_id.account_type in (
        #                     "asset_receivable",
        #                     "liability_payable"
        #                 )
        #                 and not l.reconciled
        #             )
        #
        #             _logger.warning(
        #                 "PARTIAL RECONCILING INVOICE=%s PAYMENT=%s INV=%s PAY=%s",
        #                 invoice.name,
        #                 payment.name,
        #                 inv_lines.ids,
        #                 pay_lines.ids,
        #             )
        #
        #             if inv_lines and pay_lines:
        #                 try:
        #
        #                     (inv_lines + pay_lines).reconcile()
        #
        #                     _logger.warning(
        #                         "PARTIAL RECONCILIATION COMPLETE: %s",
        #                         invoice.name
        #                     )
        #
        #                 except Exception as e:
        #
        #                     _logger.exception(
        #                         "PARTIAL RECONCILIATION FAILED: %s",
        #                         str(e)
        #                     )
        #
        #         remaining_amount -= allocated_amount
        #
        #     batch.line_ids.mapped("payment_id").write({
        #         "batch_payment_state": "partial"
        #     })


        # =====================================================
        # AUDIT TRAIL
        # =====================================================
        batch.message_post(
            body=_(
                "Payment received.<br/>"
                "Amount Due: %s<br/>"
                "Amount Received: %s<br/>"
                "Difference: %s"
            ) % (
                     batch.amount_due,
                     self.amount_received,
                     self.difference
                 )
        )

        return {
            "type": "ir.actions.client",
            "tag": "reload"
        }