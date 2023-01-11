# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _


class ResCompany(models.Model):
    _inherit = "res.company"

    rental_invoice_terms = fields.Text(string='Default Terms and Conditions For Rental Invoice', translate=True)
