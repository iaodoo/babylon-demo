# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

# ===========================
# Purchase Order Lines
# ===========================

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    account_id = fields.Many2one('account.account', string='Account')

    @api.onchange('product_id')
    def onchange_product_account_id(self):
        account_id = False
        if self.product_id.property_account_expense_id:
            account_id = self.product_id.property_account_expense_id.id
        else:
            account_id = self.product_id.categ_id.property_account_expense_categ_id.id
        self.account_id = account_id
    
    def _prepare_account_move_line(self, move=False):
        res = super(PurchaseOrderLine, self)._prepare_account_move_line()
        res['account_id'] = self.account_id
        return res
