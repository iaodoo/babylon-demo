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
    
    def action_set_lost(self, **additional_values):
        """ Lost semantic: probability = 0 or active = False """
        res = self.action_archive()
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

  