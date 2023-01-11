# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.constrains('payment_method_id', 'partner_bank_id')
    def _check_partner_bank_account(self):
        for rec in self:
            if rec.payment_method_id == self.env.ref('l10n_au_aba.account_payment_method_aba_ct'):
                if rec.partner_bank_id.acc_type != 'aba' or not rec.partner_bank_id.aba_bsb:
                    raise ValidationError(_("The partner requires a bank account with a valid BSB and account number. Please configure it first. (%s)", rec.partner_id.name))
