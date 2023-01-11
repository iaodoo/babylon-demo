# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class AccountMove(models.Model):

    _inherit = 'account.move'

    def _get_name_invoice_report(self):
        self.ensure_one()
        if self.is_rental_order_invoice:
            return 'ia_sale_report.report_rental_invoice_document'
        return super()._get_name_invoice_report()

    def get_current_user(self):
        """ For Invoice Mail Template to get current user """
        return self.env.user
