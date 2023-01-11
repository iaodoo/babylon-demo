# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
import logging

from psycopg2 import sql, DatabaseError
from lxml import etree
from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import ValidationError, UserError
from odoo.addons.base.models.res_partner import WARNING_MESSAGE, WARNING_HELP
from datetime import date, timedelta, datetime
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"
    # def update_order(self):
    #     return True
    # @api.model
    # def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
    #     res = super(SaleOrder, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
    #     if view_type == 'form' and self._context.get('default_is_rental_order', 0) == 1:
    #         fields = res.get('fields')
    #         if fields.get('order_line', False):
    #              res['fields']['order_line']['views']['tree']['fields']['price_unit']['string'] = "Weekly Rate"
    #              res['fields']['order_line']['views']['form']['fields']['price_unit']['string'] = "Weekly Rate"           
    #     return res
    

    order_maps = fields.Html(string='Maps')

    @api.depends('state', 'order_line', 'order_line.product_uom_qty', 'order_line.qty_delivered', 'order_line.qty_returned','in_out_sheets.state')
    def _compute_rental_status(self):
        # TODO replace multiple assignations by one write?
        for order in self:
            if order.state in ['sale', 'done'] and order.is_rental_order:
                rental_order_lines = order.order_line.filtered('is_rental')
                pickeable_lines = rental_order_lines.filtered(lambda sol: sol.qty_delivered < sol.product_uom_qty)
                returnable_lines = rental_order_lines.filtered(lambda sol: sol.qty_delivered and sol.qty_returned < sol.qty_delivered)
                min_pickup_date = min(pickeable_lines.filtered(lambda sol: sol.pickup_date and sol.rental_status == 'draft').mapped('pickup_date') or [datetime.today()]) if pickeable_lines else False
                min_return_date = min(returnable_lines.filtered(lambda sol: sol.return_date and sol.rental_status == 'picked').mapped('return_date') or [datetime.today()]) if returnable_lines else False
                
                if pickeable_lines and (not returnable_lines or (min_pickup_date and min_pickup_date <= min_return_date)):
                    order.rental_status = 'pickup'
                    order.next_action_date = min_pickup_date
                elif returnable_lines:
                    order.rental_status = 'return'
                    order.next_action_date = min_return_date
                elif pickeable_lines and not returnable_lines:
                    order.rental_status = 'pickup'
                    order.next_action_date = min_pickup_date
                # elif not pickeable_lines and not returnable_lines:
                #     order.rental_status = 'pickup'
                #     order.next_action_date = min_pickup_date
                else:
                    order.rental_status = 'returned'
                    order.next_action_date = False
                order.has_pickable_lines = bool(pickeable_lines)
                order.has_returnable_lines = bool(returnable_lines)
                for sheets in order.in_out_sheets:
                    if sheets.state =='outdone' and not returnable_lines:
                        order.rental_status = 'wpu'
                    elif not returnable_lines and  order.rental_status == 'pickup' and sheets.state =='out':
                        order.rental_status = 'wha'
                rental_status = False
                for line in rental_order_lines:
                    if line.rental_status == 'returned':
                        rental_status = True
                    else:
                        rental_status = False
                        break
                if rental_status:
                    order.rental_status = 'returned'

            else:
                order.has_pickable_lines = False
                order.has_returnable_lines = False
                order.rental_status = order.state if order.is_rental_order else False
                order.next_action_date = False


    rental_status = fields.Selection(selection_add=[('wha', 'Waiting Out Sheet'), ('wpu', 'Waiting Pick Up'), ('return',)])
    in_out_sheets = fields.One2many('ia.inout.sheet', 'sale_order_id', string='IN OUT Sheet', copy=False)

    quote_type = fields.Selection([
        ('sale', "Sale"),
        ('project', "Project"),
        ('transport', "Transport")], default=False, string="Quote Type")


    wait_hire_agreement = fields.Boolean(string="Waiting Hire Agreement", compute="_compute_has_sheet_lines", copy=False)

    @api.depends('is_rental_order', 'in_out_sheets.state')
    def _compute_has_sheet_lines(self):
        for order in self:
            order.wait_hire_agreement = False
            for sheets in order.in_out_sheets:
                if sheets.state =='outdone':
                    order.wait_hire_agreement = True
                else:
                    order.wait_hire_agreement = False
            if order.rental_status != 'wpu':
                order.wait_hire_agreement = False
 

    # @api.model
    # def create(self, vals):
    #     if "quote_type" in vals:
    #         if vals.get("quote_type") == 'sale':
    #             vals["name"] = self.env["ir.sequence"].next_by_code("sale.quotation") or "/"
    #         if vals.get("quote_type") == 'project':
    #             vals["name"] = self.env["ir.sequence"].next_by_code("project.quotation") or "/"
    #     if "is_rental_order" in vals:
    #         if vals.get('is_rental_order'):
    #             vals["name"] = self.env["ir.sequence"].next_by_code("hire.quotation") or "/"
    #     return super(SaleOrder, self).create(vals)
    
    @api.model
    def create(self, vals):
        name = self.env["ir.sequence"].next_by_code("sale.quotation") or "/"
        if "quote_type" in vals:
            if vals.get("quote_type") == 'sale':
                vals["name"] = name + 'S'
            if vals.get("quote_type") == 'project':
                vals["name"] = name + 'P'
            if vals.get("quote_type") == 'transport':
                vals["name"] = name + 'T'
        if "is_rental_order" in vals:
            if vals.get('is_rental_order'):
                vals["name"] = name + 'H'
        return super(SaleOrder, self).create(vals)

    def copy(self, default=None):
        self.ensure_one()
        if default is None:
            default = {}
        default["name"] = "/"
        if self.origin and self.origin != "":
            default["origin"] = self.origin + ", " + self.name
        else:
            default["origin"] = self.name
        return super(SaleOrder, self).copy(default)
    # def open_pickup(self):
    #     for order in self:
    #         if not order.in_out_sheets:
    #            raise UserError(_('Please complete OUT Sheet before Pickup'))
    #         for sheets in order.in_out_sheets:
    #             if sheets.state in ('draft','out'):
    #                 raise UserError(_('Please complete OUT Sheet before Pickup'))
    #             else:
    #                     sheets.write({'state':'onhire'})

    #     return super(SaleOrder, self).open_pickup()
    
    # def open_return(self):
    #     for order in self:
    #         for sheets in order.in_out_sheets:
    #                 if sheets.state in ('draft','out','outdone','onhire'):
    #                     raise UserError(_('Please complete IN Sheet before Return'))
    #                 else:
    #                     sheets.write({'state':'hiredone'})

    #     return super(SaleOrder, self).open_return()
    
    def _action_confirm(self):
        res =  super(SaleOrder, self)._action_confirm()
        for order in self:
            if not order.client_order_ref:
                raise UserError(_('Please add PO Number before order confirming'))

            if not order.in_out_sheets:
                order.in_out_sheets.create({'sale_order_id':order.id,'partner_id':order.partner_id.id,'state':'draft'})
                
            if order.quote_type in ['sale', 'project']:
                if order.project_id:
                    order.project_id.active = True
                else:
                    order._create_project_from_sale_order()
                
                # Assign Analytic Tags to Sale/Project Orders
                tank_tags = self.env['account.analytic.tag'].search([('name','=','Tank Sales')])
                if tank_tags:
                    for lines in order.order_line:
                        lines.write({'analytic_tag_ids':[(6,0,tank_tags.ids)]})
            
            # Assign Analytic Tags to Transport Orders
            if order.quote_type == 'transport':
                tran_tags = self.env['account.analytic.tag'].search([('name','=','Transport')])
                if tran_tags:
                    for lines in order.order_line:
                        lines.write({'analytic_tag_ids':[(6,0,tran_tags.ids)]})
            
            # Assign Analytic Tags to Rental Orders
            if order.is_rental_order:
                hire_tags = self.env['account.analytic.tag'].search([('name','=','Tank Hire')])
                if hire_tags:
                    for lines in order.order_line:
                        lines.write({'analytic_tag_ids':[(6,0,hire_tags.ids)]}) 

        return res

    def _create_project_from_sale_order(self):
        self.ensure_one()
        project = self.env['project.project'].with_context(auto_create_analytic_account=True).create({
            'name': self.name,
        })
        self.project_id = project and project.id or False
        self.analytic_account_id = project and project.analytic_account_id and project.analytic_account_id.id or False

    def write(self, values):
        if 'state' in values and values['state'] == 'cancel':
            if self.project_id:
                self.project_id.active = False
        return super(SaleOrder, self).write(values)
    
    def action_view_in_out_sheet(self):
        action = self.env["ir.actions.actions"]._for_xml_id("ia_crm_custom.ia_inout_sheet_action")
        action['context'] = {
            'default_partner_id': self.partner_id.id,
            'default_sale_order_id': self.id
        }
        in_out_sheets = self.in_out_sheets
        lots = []
        for line in self.order_line.filtered(lambda o: o.reserved_lot_ids):
            for lot_id in line.reserved_lot_ids:
                lots.append(lot_id.id)
        if lots: 
            for sheet in  in_out_sheets:  
                if not sheet.ia_picked_lot_ids:         
                   sheet.write({'ia_reserved_lot_ids':[(6,0,lots)],'ia_picked_lot_ids':[(6,0,lots)]})
                if sheet.state not in ('hiredone'):
                   sheet.write({'ia_reserved_lot_ids':[(6,0,lots)]})
                action['context']['default_ia_reserved_lot_ids'] = [(6,0,lots)]
                action['context']['default_ia_picked_lot_ids'] = [(6,0,lots)]       
        if len(in_out_sheets.ids) > 1:
            action['domain'] = [('id', 'in', in_out_sheets.ids)]
        elif len(in_out_sheets) == 1:
            res = self.env.ref('ia_crm_custom.ia_inout_sheet_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = in_out_sheets.id
        else:
            action['res_id'] = False
        return action

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        super(SaleOrder, self).onchange_partner_id()
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

# ========================
# Serial Numbers
# ========================
class SerialNumbers(models.Model):
    _inherit = "stock.production.lot"
#  ('draft', 'Quotation'),
#         ('sent', 'Quotation Sent'),
#         ('pickup', 'Waiting Hire Agreement'),
#         ('wha', 'Waiting Out Sheet'),
#         ('wpu', 'Waiting Pick Up'),
#         ('return', 'Picked-up'),
#         ('returned', 'Returned'),
#         ('cancel', 'Cancelled'),
    rental_status = fields.Selection([
        ('draft', 'Quotation'),     
        ('picked', 'Picked-up'),
        ('returned', 'Returned'),
        ('cancel', 'Cancelled'),       
    ], string="Rental Status", compute='_find_rental_status')
    return_date = fields.Datetime("Expected Return Date", compute='_find_rental_status')

    def _find_rental_status(self):
        for lot in self:
            status = ''
            lot.return_date = False
            order_lines = self.env['sale.order.line'].search([('order_id.is_rental_order','=',True),('state','!=','cancel'),('rental_reserved_lot_id','=', lot.id)], order = "return_date desc", limit =1)
            for line in order_lines:              
                    status = line.rental_status
                    lot.return_date = line.return_date
                    break
            lot.rental_status = str(status)
