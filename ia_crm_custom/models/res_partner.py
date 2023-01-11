# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.tools import config


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.constrains('company_type')
    def check_company_type(self):
        for partner in self:
            if config["test_enable"]:
                continue
            if not partner.parent_id and partner.company_type == 'person':
                raise ValidationError(
                    _("Please assign individual contacts to be a parent company or create as company record ")
                )
