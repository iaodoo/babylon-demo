# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rental_invoice_terms = fields.Text(related='company_id.rental_invoice_terms',
                                       string="Terms & Conditions For Rental", readonly=False)
    use_rental_invoice_terms = fields.Boolean(
        string='Default Terms & Conditions For Rental',
        config_parameter='account.use_rental_invoice_terms')
