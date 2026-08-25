"""Chart of accounts template hooks for waste management setup."""
from odoo import models

class AccountChartTemplate(models.AbstractModel):
    """Extend account chart loading for waste-specific accounts."""
    _inherit = "account.chart.template"

    def _load(self, template_code, company, install_demo=False):
        # 🚫 BLOCK chart template ONLY for branches
        if company.is_branch:
            return

        return super()._load(template_code, company, install_demo)