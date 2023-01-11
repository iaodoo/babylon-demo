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


class Lots(models.Model):
    _inherit = "stock.production.lot"

    @api.depends('quant_ids', 'quant_ids.quantity')
    def _compute_current_location_id(self):
        for lot in self:
            quants = self.env['stock.quant'].search([('id', 'in', lot.quant_ids.ids), ('quantity', '>', '0')], limit=1,
                                                    order='in_date desc')
            if quants and quants[0]:
                lot.current_location_id = quants[0].location_id.id
            else:
                lot.current_location_id = False

    home_depot_id = fields.Many2one('stock.location', 'Home Depot')
    current_location_id = fields.Many2one('stock.location', 'Current Location', compute='_compute_current_location_id')
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", copy=False,
                                          ondelete='set null',
                                          domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
                                          check_company=True)

    @api.model_create_multi
    def create(self, vals_list):
        """ Create an analytic account if lot is created
        """
        defaults = self.default_get(['analytic_account_id'])
        for values in vals_list:
            analytic_account_id = values.get('analytic_account_id', defaults.get('analytic_account_id'))
            if not analytic_account_id:
                analytic_account = self._create_analytic_account_from_values(values)
                values['analytic_account_id'] = analytic_account.id
        return super(Lots, self).create(vals_list)

    def unlink(self):
        analytic_account = self.analytic_account_id
        res = super(Lots, self).unlink()
        analytic_account.write({'active': False})
        return res

    @api.model
    def _create_analytic_account_from_values(self, values):
        analytic_account = self.env['account.analytic.account'].create({
            'name': values.get('name', _('Unknown Analytic Account')),
            'company_id': values.get('company_id') or self.env.company.id,
            'active': True,
        })
        return analytic_account

    def action_view_analytic_account(self):
        action = self.env["ir.actions.actions"]._for_xml_id("analytic.action_account_analytic_account_form")
        if self.analytic_account_id:
            form_view = [(self.env.ref('analytic.view_account_analytic_account_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = self.analytic_account_id.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
