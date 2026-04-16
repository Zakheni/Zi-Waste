from odoo import models, _
from odoo.exceptions import UserError

class HrJob(models.Model):
    _inherit = "hr.job"

    def unlink(self):
        if self.env.user.has_group('waste_management_zakheni.group_company_admin'):
            raise UserError(_("You are not allowed to delete Job."))
        return super().unlink()
