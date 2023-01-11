# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
import logging

from psycopg2 import sql, DatabaseError

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import ValidationError
from odoo.addons.base.models.res_partner import WARNING_MESSAGE, WARNING_HELP

_logger = logging.getLogger(__name__)

class Stage(models.Model):
   
    _inherit = "crm.stage" 
    is_lost = fields.Boolean('Is Lost Stage?')

class Lead(models.Model):
    _inherit = "crm.lead"
    _order = "quote_ref desc, priority desc, id desc"
    
    quote_ref = fields.Char('Quote Reference')
    quotation_count = fields.Integer(compute='_compute_sale_data', string="Number of Quotations")
    is_lost = fields.Boolean(related='stage_id.is_lost', string='Lost')

    def action_view_sale_quotation(self):
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations_with_onboarding")
        action['context'] = {
            'search_default_draft': 1,
            'search_default_partner_id': self.partner_id.id,
            'default_partner_id': self.partner_id.id,
            'default_opportunity_id': self.id
        }
        action['domain'] = [('opportunity_id', '=', self.id), ('state', 'in', ['draft', 'sent', 'cancel'])]
        quotations = self.mapped('order_ids').filtered(lambda l: l.state in ('draft', 'sent', 'cancel'))
        if len(quotations) == 1:
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
            action['res_id'] = quotations.id
        return action #super(Lead, self).action_view_sale_quotation(self)
    
    def action_set_lost(self, **additional_values):
        """ Lost semantic: probability = 0 or active = False """
        #res = self.action_archive() 
        res = self.action_unarchive() # Custom to block archiving of the opportunity
        leads_by_lost_stage = {}
        for lead in self:
            stage_id = lead._stage_find(domain=[('is_lost', '=', True)])
            if stage_id in leads_by_lost_stage:
                leads_by_lost_stage[stage_id] |= lead
            else:
                leads_by_lost_stage[stage_id] = lead
        for won_stage_id, leads in leads_by_lost_stage.items():
            leads.write({'stage_id': won_stage_id.id})
        if additional_values:
            self.write(dict(additional_values))
        return res

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        res = {}
        if not self.partner_id:
            return
        show_warning = False
        if self.partner_id.parent_id:
            if not self.partner_id.parent_id.has_account:
                show_warning = True
        else:
            if not self.partner_id.has_account:
                show_warning = True
        if show_warning:
            res['warning'] = {
                'title': _('Warning'),
                'message': _(
                    'Organisation / Contact selected does not have an Account. Please ensure the contact is not a '
                    'duplicate or confirm with WTA admin that no account exists.')
            }
        return res

class Partner(models.Model):
    _inherit = "res.partner"
    has_account = fields.Boolean(string="Has Account", tracking=True)
    
