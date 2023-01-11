# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
import time
import logging

from psycopg2 import sql, DatabaseError

from odoo import api, fields, models, _
_logger = logging.getLogger(__name__)
class PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    READ_STATES = {
        'draft': [('readonly', False)],    
        'cancel': [('readonly', False)],
    }
    name = fields.Char('Order Reference', required=True, index=True, copy=False, default='New', readonly = True, states=READ_STATES,)
