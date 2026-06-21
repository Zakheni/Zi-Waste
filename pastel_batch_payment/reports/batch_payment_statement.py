from odoo import models


class BatchPaymentStatement(models.AbstractModel):
    _name = "report.pastel_batch_payment.batch_payment_statement"
    _description = "Batch Payment Statement"

    def _get_report_values(self, docids, data=None):

        docs = self.env["batch.payment"].browse(docids)

        return {
            "doc_ids": docs.ids,
            "doc_model": "batch.payment",
            "docs": docs,
        }