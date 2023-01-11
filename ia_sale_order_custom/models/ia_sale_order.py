# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from email.policy import default
import re
import time
import logging
import pytz
from psycopg2 import sql, DatabaseError

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import ValidationError, UserError
from odoo.addons.base.models.res_partner import WARNING_MESSAGE, WARNING_HELP
from datetime import date, timedelta, datetime
import calendar
from odoo.tools import float_is_zero, float_compare, format_datetime, format_time
from pytz import timezone, UTC
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def _prepare_invoice_values(self, order, name, amount, so_line):
        res = super(SaleAdvancePaymentInv, self)._prepare_invoice_values(order, name, amount, so_line)
        if not order.note and order.is_rental_order:
            res['narration'] = order.company_id.with_context(
                lang=order.partner_id.lang or self.env.lang).rental_invoice_terms
        else:
            res['narration'] = self.env['ir.config_parameter'].sudo().get_param('account.use_invoice_terms') and self.env.company.invoice_terms or ''
        return res
        


class RentalPricing(models.Model):
    _inherit = 'rental.pricing'
    price = fields.Float(string="Price", required=True, default=1.0, digits=(16,4))

class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.depends('is_rental_order', 'next_action_date', 'rental_status')
    def _compute_has_late_lines(self):
        for order in self:
            # if order.state in ['sale', 'done'] and order.is_rental_order:
            #     order.next_action_date = date.today()
            order.has_late_lines = (
                order.is_rental_order
                and order.rental_status in ['pickup', 'return']  # has_pickable_lines or has_returnable_lines
                and order.next_action_date and order.next_action_date < fields.Datetime.now())



    @api.depends('order_line.product_id', 'order_line.reserved_lot_ids','order_line.pickup_date','order_line.return_date')
    def _compute_reserved_lot_ids(self):
        for order in self:
            order.reserved_lot_ids = []
            order.pickup_date = False
            order.return_date = False
            order.last_invoice_date - False
            if order.invoice_ids:
                order.last_invoice_date = max(order.invoice_ids.filtered(lambda sol: sol.invoice_date).mapped('invoice_date'))                
            order_line = order.order_line.filtered(lambda t: t.product_id and t.pickup_date and t.return_date)
            max_pickup_date = max(order_line.filtered(lambda sol: sol.pickup_date).mapped('pickup_date')) if order_line else False
            max_return_date = max(order_line.filtered(lambda sol: sol.return_date).mapped('return_date')) if order_line else False                
            order.reserved_lot_ids = [(6, 0, [x.id for x in order_line.reserved_lot_ids])]
            order.pickup_date = max_pickup_date
            order.return_date = max_return_date
            order.return_date_1 = max_return_date and (max_return_date - timedelta(seconds=1)) or False
                
    actual_return_date = fields.Datetime(string="Actual Return Date", copy=False)      
    reserved_lot_ids = fields.Many2many('stock.production.lot', 'ia_rental_reserved_lot_rel',compute='_compute_reserved_lot_ids', copy=False, compute_sudo=True)
    pickup_date = fields.Datetime(string="Last Pickup Date",compute='_compute_reserved_lot_ids', copy=False, store = True, compute_sudo=True)
    return_date = fields.Datetime(string="Last Return Date",compute='_compute_reserved_lot_ids', copy=False, store = True, compute_sudo=True)
    return_date_1 = fields.Datetime(string="Last Return Date - 1s",compute='_compute_reserved_lot_ids', copy=False, store = True, compute_sudo=True)
    site_location = fields.Char(string='Site Location', readonly=False)
    cover_business_name = fields.Char(string='Business Name')
    cover_contact_name = fields.Char(string='Contact Name')
    cover_date_order = fields.Datetime(string='Date')
    cover_equipment_details = fields.Char(string='Equipment Details')
    last_invoice_date = fields.Date(string="Last Invoiced",compute='_compute_reserved_lot_ids', copy=False, store = False, compute_sudo=True)
    client_order_ref = fields.Char(string='PO Number', copy=False, tracking="1")
    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Invoice Posted'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
    ], string='Invoice Status', compute='_compute_invoice_status', store=True, readonly=True, default='no')
    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        res['site_location'] = self.site_location
        res['is_rental_order_invoice'] = self.is_rental_order
        if not self.note and self.is_rental_order:
            res['narration'] = self.company_id.with_context(
                lang=self.partner_id.lang or self.env.lang).rental_invoice_terms
        else:
            res['narration'] = self.env['ir.config_parameter'].sudo().get_param('account.use_invoice_terms') and self.env.company.invoice_terms or ''
        return res

    @api.model
    def _default_note(self):
        notes = '' #self.env['ir.config_parameter'].sudo().get_param('account.use_invoice_terms') and self.env.company.invoice_terms or ''
        #if not notes and self._context.get('default_is_rental_order',False)==1:
           #notes = self.env.user.company_id.with_context(
           #     lang=self.partner_id.lang or self.env.lang).rental_invoice_terms
        if self._context.get('default_is_rental_order',False) == 1:
           notes = ''
        return notes

    note = fields.Text('Terms and conditions', default=_default_note)

    def open_return(self):
        for line in self.order_line:
            line.write({'quote_pickup_date': line.pickup_date,'quote_return_date': line.return_date})
        return super(SaleOrder, self).open_return()
    

   
    def _get_invoiceable_lines(self, final=False):
        """Return the invoiceable lines for order `self`."""
        down_payment_line_ids = []
        invoiceable_line_ids = []
        pending_section = None
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        for line in self.order_line:
            # if line.product_id.invoice_monthly and self.is_rental_order:
            #         continue
            if line.rental_invoiced and self.is_rental_order:
                continue
            if line.display_type == 'line_section':
                # Only invoice the section if one of its lines is invoiceable
                pending_section = line
                continue
            if not self.is_rental_order:
                if line.display_type == 'line_note' and float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    continue
                if line.display_type != 'line_note' and float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    continue
            #    [WTA] Invoicing Error (#8796)
            #or (line.qty_to_invoice < 0)
            if not self.is_rental_order:
                if line.qty_to_invoice > 0  or line.display_type == 'line_note':
                    if line.is_downpayment:
                        # Keep down payment lines separately, to put them together
                        # at the end of the invoice, in a specific dedicated section.
                        down_payment_line_ids.append(line.id)
                        continue
                    if pending_section:
                        invoiceable_line_ids.append(pending_section.id)
                        pending_section = None
            else:
                if line.is_downpayment:
                    # Keep down payment lines separately, to put them together
                    # at the end of the invoice, in a specific dedicated section.
                    down_payment_line_ids.append(line.id)
                    continue
                if pending_section:
                    invoiceable_line_ids.append(pending_section.id)
                    pending_section = None

            invoiceable_line_ids.append(line.id)

        return self.env['sale.order.line'].browse(invoiceable_line_ids + down_payment_line_ids)    

        
class RentalProcessingLine(models.TransientModel):
    _inherit = 'rental.order.wizard.line'
    # actual_return_date = fields.Datetime(string="Return Date", default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hours=1))
    # actual_pickup_date = fields.Datetime(string="Pickup Date", default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hours=1))
    actual_return_date = fields.Datetime(string="Return Date")
    actual_pickup_date = fields.Datetime(string="Pickup Date")

    rental_lot_id = fields.Many2one('stock.production.lot', string="Serial Number",
                                    help="Only available serial numbers are suggested.", domain="[('id', 'in', pickeable_lot_ids)]")
    rental_returned_lot_id = fields.Many2one('stock.production.lot', domain="[('id', 'in', returnable_lot_ids)]")
    

    @api.onchange('actual_pickup_date')
    def _rental_actual_pickup_date(self):
        if self.actual_pickup_date:  
            pickup_date = self.actual_pickup_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)
            # time_timezone = format_time(self.with_context(use_babel=True).env, pickup_date, tz=self.env.user.tz, time_format=False)
            # time_timezone = time_timezone.split(':')
            pickup_date = datetime.combine(pickup_date, datetime.min.time())
           # pickup_date = pickup_date - timedelta(hours=int(time_timezone[0]),minutes = int(time_timezone[1]),seconds = int(time_timezone[2]))      
            user_date = datetime.now(pytz.timezone(self.env.user.tz or 'UTC'))
            utc_diff = user_date.utcoffset().total_seconds()/60/60
            self.actual_pickup_date = pickup_date - timedelta(hours=utc_diff)
    

    @api.onchange('actual_return_date')
    def _rental_actual_return_date(self):
        if self.actual_return_date: 
            return_date = self.actual_return_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)
            # time_timezone = format_time(self.with_context(use_babel=True).env, return_date, tz=self.env.user.tz, time_format=False)
            # time_timezone = time_timezone.split(':')
            return_date = datetime.combine(return_date, datetime.max.time())      
            # return_date = return_date - timedelta(hours=int(time_timezone[0]),minutes = int(time_timezone[1]),seconds = int(time_timezone[2]))
            # self.actual_return_date = return_date
            user_date = datetime.now(pytz.timezone(self.env.user.tz or 'UTC'))
            utc_diff = user_date.utcoffset().total_seconds()/60/60
            self.actual_return_date = return_date - timedelta(hours=utc_diff)
    

    @api.onchange('pickedup_lot_ids')
    def _rental_pickedup_lot_ids(self):
        if self.pickedup_lot_ids:
            self.rental_lot_id = self.pickedup_lot_ids.ids[0]

    @api.onchange('rental_lot_id')
    def _rental_lot_id(self):
        if self.rental_lot_id:
            self.pickedup_lot_ids = [(6, 0, [self.rental_lot_id.id])]
        else:
            self.pickedup_lot_ids = False
    @api.onchange('rental_returned_lot_id')
    def _rental_returned_lot_id(self):         
        if not self.rental_returned_lot_id and  self.tracking == 'serial':
            self.qty_returned = 0
            self.returned_lot_ids = False
      
    @api.model
    def _default_wizard_line_vals(self, line, status):
        res = super(RentalProcessingLine, self)._default_wizard_line_vals(line, status)  
        res['rental_lot_id']= (res['pickedup_lot_ids'] and res['pickedup_lot_ids'][0][2]) and res['pickedup_lot_ids'][0][2][0] or False
        res['rental_returned_lot_id'] = res['rental_lot_id']        
        return res 

    def _apply(self):
        res = super(RentalProcessingLine, self)._apply()
        
        for wizard_line in self:
            order_line = wizard_line.order_line_id
            if wizard_line.status == 'pickup' and wizard_line.qty_delivered > 0:
                if  wizard_line.tracking == 'serial' and wizard_line.rental_lot_id:
                    if not order_line.order_id.in_out_sheets:
                        raise UserError(_('Please complete OUT Sheet before Pickup'))
                    found_data = False
                    serial_numbers = ''
                    for sheets in order_line.order_id.in_out_sheets:
                        if sheets.state in ('outdone','onhire') and wizard_line.rental_lot_id.id in sheets.ia_picked_lot_ids.ids:
                            found_data = True 
                            sheets.write({'state':'onhire'})                       
                            break
                        serial_numbers += str(wizard_line.rental_lot_id.name) + ", "
                    if not found_data:
                        raise UserError(_('Please complete OUT Sheet before Pickup. '))
        #for sheets in order.in_out_sheets:
    #                 if sheets.state in ('draft','out','outdone','onhire'):
    #                     raise UserError(_('Please complete IN Sheet before Return'))
    #                 else:
    #                     sheets.write({'state':'hiredone'})

            if wizard_line.status == 'return' and wizard_line.qty_returned > 0:
                if wizard_line.tracking == 'serial' and wizard_line.rental_returned_lot_id:                   
                    found_data = False
                    serial_numbers = ''
                    for sheets in order_line.order_id.in_out_sheets:
                        if sheets.state in ('in','hiredone') and wizard_line.rental_returned_lot_id.id in sheets.ia_returned_lot_ids.ids:
                            found_data = True 
                            sheets.write({'state':'hiredone'})                       
                            break
                        serial_numbers += str(wizard_line.rental_lot_id.name) + ", "
                    if not found_data:
                        raise UserError(_('Please complete IN Sheet before Return.'))


            order_line = wizard_line.order_line_id
            if wizard_line.status == 'pickup' and wizard_line.qty_delivered > 0:
                order_line.price_unit = order_line._compute_unit_price_rental() * order_line.product_uom_qty
                if not wizard_line.actual_pickup_date and wizard_line.rental_lot_id:
                    raise ValidationError(_("Please enter actual pickup date for the serial number "+str(wizard_line.rental_lot_id.name)))
                if wizard_line.actual_pickup_date:
                    order_line.pickup_date = wizard_line.actual_pickup_date
                    if  order_line.return_date< order_line.pickup_date:
                        order_line.return_date = wizard_line.actual_pickup_date + timedelta(days=1)
                order_line.name = order_line.get_sale_order_line_multiline_description_sale(order_line.product_id)
                order_line.write({'rental_status': 'picked'})                
            if wizard_line.status == 'return' and wizard_line.qty_returned > 0:
                if not wizard_line.actual_return_date and wizard_line.rental_returned_lot_id:
                    raise ValidationError(_("Please enter actual return date for the serial number "+str(wizard_line.rental_returned_lot_id.name)))
                if wizard_line.actual_return_date:
                    order_line.return_date = wizard_line.actual_return_date
                    actual_return_date =  (wizard_line.actual_return_date - timedelta(seconds=1))
                    order_line.order_id.write({'actual_return_date': actual_return_date})
                if order_line.rental_duration:
                    order_line.price_unit = order_line._compute_unit_price_rental() * order_line.product_uom_qty
                order_line.name = order_line.get_sale_order_line_multiline_description_sale(order_line.product_id)
                order_line.write({'rental_status': 'returned'})
               
                         

        return res  

class ProductTemplate(models.Model):   
    _inherit = "product.template" 
    invoice_monthly = fields.Boolean(string='Invoice Monthly')
    hide_days = fields.Boolean(string='Hide Days')


class AccountMoveLine(models.Model):   
    _inherit = "account.move.line" 
    hide_in_quote = fields.Boolean(string='Hide in Quote')
    hide_days = fields.Boolean(string='Hide Days')
    
    @api.onchange('product_id')
    def _change_product_id(self):
        if self.product_id:
            self.hide_days = self.product_id.hide_days


class AccountMove(models.Model):   
    _inherit = "account.move"
    site_location = fields.Char(string='Site Location', readonly=False)
 
class SaleOrderLine(models.Model):   
    _inherit = "sale.order.line" 

    def init(self):
       
        res = self._cr.execute("""
            update sale_order_line set rental_status = 'picked' where rental_status = 'draft' and order_id in (select id from sale_order where rental_status = 'return')           
            """)
        res = self._cr.execute("""
            update sale_order_line set rental_status = 'returned' where rental_status = 'draft' and order_id in (select id from sale_order where rental_status = 'returned')           
            """)

    supplier_partner_id = fields.Many2one('res.partner', string="Supplier")
    muv_per = fields.Float(string='MUV%')
    unit_muv = fields.Float(string='Unit MUV')
    unit_cost = fields.Float(string='Unit Cost')
    quantity_cost = fields.Float(string='Qty Cost')
    quantity_muv = fields.Float(string='Qty MUV')
    rental_duration = fields.Float(string='Weeks', compute='_compute_duration_wizard', store = True, digits=(0, 4))   
    weekly_rate = fields.Float(string='Weekly Rate', compute='_compute_weekly_rate', store = True, digits=(0, 2))   
   # weekly_qty = fields.Float(string='Weekly Qty', compute='_compute_weekly_qty', store = True, digits=(0, 4))   
    quote_pickup_date = fields.Datetime(string="Quote Pickup")
    quote_return_date = fields.Datetime(string="Quote Return")  
    #unit_price = fields.Float(string='Weekly Rate', compute='_compute_unit_price_rental', store = True)   
    hide_in_quote = fields.Boolean(string='Hide in Quote')
    daily_rate = fields.Float(string='Daily Rate', compute='_compute_weekly_rate', store = True, digits=(0, 2))   
    rental_reserved_lot_id = fields.Many2one('stock.production.lot',copy=False, string="Reserved Lot", help="Only available serial numbers are suggested.", domain="[('product_id', '=', product_id)]")

    rental_status = fields.Selection([
        ('draft', 'Quotation'),     
        ('picked', 'Picked-up'),
        ('returned', 'Returned'),
        ('cancel', 'Cancelled'),
    ], string="Rental Status", default="draft")

    rental_invoiced = fields.Boolean(string='Rental Invoiced')

    @api.onchange('rental_reserved_lot_id')
    def _rental_reserved_lot_id(self):
        if self.rental_reserved_lot_id:
            self.reserved_lot_ids = [(6, 0, [self.rental_reserved_lot_id.id])]

    @api.onchange('reserved_lot_ids')
    def _reserved_lot_ids(self):
        if self.reserved_lot_ids:
            self.rental_reserved_lot_id = self.reserved_lot_ids.ids[0]

    def _prepare_invoice_line(self, **optional_values):       
        res = super(SaleOrderLine, self)._prepare_invoice_line()
        res['hide_in_quote'] = self.hide_in_quote
        res['pickup_date'] = self.pickup_date
        res['return_date'] = self.return_date
        #    [WTA] Invoicing Error (#8796)
        if self.order_id.is_rental_order:
            res['quantity'] = self.product_uom_qty        
        return res

    

    @api.depends('order_id.pricelist_id', 'pickup_date', 'return_date')
    def _compute_duration_wizard(self):
        for line in self:
            values = {                
                'rental_duration': 1.0,
            }
            if line.pickup_date and line.return_date:
                pricing_id = line.product_id._get_best_pricing_rule(
                    pickup_date=line.pickup_date,
                    return_date=line.return_date,
                    pricelist=line.order_id.pricelist_id,
                    company=line.order_id.company_id)
                duration_dict = self.env['rental.pricing']._compute_duration_vals(line.pickup_date, line.return_date)
                if pricing_id:
                    if pricing_id.unit == 'day':
                        values = {                    
                            'rental_duration': duration_dict[pricing_id.unit] /7                  
                            }
                    else:
                        values = {                    
                            'rental_duration': duration_dict[pricing_id.unit]                
                            }

                else:
                    values = {                     
                        'rental_duration': duration_dict['day']/7
                    }
            line.update(values)

    # @api.onchange('rental_duration', 'pickup_date', 'return_date')
    # def _compute_unit_price(self):
    #     for line in self:
    #         if line.pickup_date and line.return_date:                
    #             line.unit_price = line.weekly_rate *  line.rental_duration
    #         else:
    #             line.unit_price = 0.0

    def _compute_unit_price_rental(self):
        for line in self:
            unit_price = 0.0
            if line.rental_duration > 0:
                if line.pickup_date and line.return_date:
                    pricing_id = line.product_id._get_best_pricing_rule(
                        pickup_date=line.pickup_date,
                        return_date=line.return_date,
                        pricelist=line.order_id.pricelist_id,
                        company=line.order_id.company_id)
                    if pricing_id:
                        unit_price = pricing_id._compute_price(int(line.rental_duration*7), pricing_id.unit)
                        if line.order_id.currency_id != pricing_id.currency_id:
                            line.unit_price = pricing_id.currency_id._convert(
                                from_amount=unit_price,
                                to_currency=line.order_id.currency_id,
                                company=line.order_id.company_id,
                                date=date.today())
                        else:
                            unit_price = unit_price
                    elif line.rental_duration > 0:
                        unit_price = line.product_id.lst_price  
            return unit_price              
    @api.depends('product_id','pickup_date','return_date')
    def _compute_weekly_rate(self):
        for line in self:
            line.weekly_rate = 0.0 
            if line.pickup_date and line.return_date:
                    pricing_id = line.product_id._get_best_pricing_rule(
                        pickup_date=line.pickup_date,
                        return_date=line.return_date,
                        pricelist=line.order_id.pricelist_id,
                        company=line.order_id.company_id)
                    if pricing_id and pricing_id.unit =='day' and line.order_id.is_rental_order:   
                        line.weekly_rate = (pricing_id.price * 7) or 0.0
                        line.daily_rate = (pricing_id.price) or 0.0
    # @api.depends('price_unit','return_date','pickup_date')
    # def _compute_weekly_qty(self):
    #     for line in self:
    #         line.weekly_qty = 0.0 
    #         if line.rental_duration and line.product_uom_qty and line.order_id.is_rental_order:   
    #             line.weekly_qty = line.product_uom_qty and (line.product_uom_qty/7) or 0.0
    @api.onchange('product_id')
    def _supplier_product_id(self):
        if self.product_id:
            self.unit_cost = self.product_id.standard_price

    @api.onchange('supplier_partner_id','muv_per','unit_cost','product_uom_qty')
    def _supplier_partner_id(self):
        #if self.supplier_partner_id and self.product_id:
        if self.unit_cost:
            #supplierinfo = self.product_id.seller_ids.filtered(lambda t: t.name and t.name.id == self.supplier_partner_id.id)
            #for res in supplierinfo:
            #    self.unit_cost = res.price
            
            self.unit_muv = self.unit_cost*(self.muv_per/100)
            self.price_unit = self.unit_cost + self.unit_muv
            self.quantity_cost = self.unit_cost * self.product_uom_qty
            self.quantity_muv = self.unit_muv * self.product_uom_qty
        #if self.supplier_partner_id and not self.order_id.is_rental_order:
        #    res = {'domain': {'product_id': [('seller_ids.name','=',self.supplier_partner_id.id)]}}
        #    return res

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        super(SaleOrderLine, self).product_uom_change()
        self._supplier_partner_id()

    @api.onchange('price_unit')
    def _onchange_price_unit(self):
        if self.price_unit:
            self.unit_muv = self.price_unit - self.unit_cost
            self.muv_per = (self.unit_muv / self.unit_cost) * 100 if self.unit_cost else 0.0

    def _move_serials(self, lot_ids, location_id, location_dest_id):
        """Move the given lots from location_id to location_dest_id.

        :param stock.production.lot lot_ids:
        :param stock.location location_id:
        :param stock.location location_dest_id:
        """
        if not lot_ids:
            return
        for lot_id in lot_ids:
            rental_stock_move = self.env['stock.move'].create({
                'product_id': self.product_id.id,
                'product_uom_qty': 1,
                'product_uom': self.product_id.uom_id.id,
                'location_id': (lot_id.home_depot_id and  location_id.usage =='internal') and lot_id.home_depot_id.id or location_id.id,
                'location_dest_id': (lot_id.home_depot_id and  location_id.usage != 'internal') and lot_id.home_depot_id.id or location_dest_id.id,
                'partner_id': self.order_partner_id.id,
                'sale_line_id': self.id,
                'name': _("Rental move :") + " %s" % (self.order_id.name),
            })
            loc_id = (lot_id.home_depot_id and  location_id.usage =='internal') and lot_id.home_depot_id or location_id
            lot_quant = self.env['stock.quant']._gather(self.product_id, loc_id, lot_id)
            lot_quant = lot_quant.filtered(lambda quant: quant.quantity == 1.0)
            if not lot_quant:
                raise ValidationError(_("No valid quant has been found in location %s for serial number %s !") % (loc_id.name, lot_id.name))
                # Best fallback strategy??
                # Make a stock move without specifying quants and lots?
                # Let the move be created with the erroneous quant???
            # As we are using serial numbers, only one quant is expected
            ml = self.env['stock.move.line'].create(rental_stock_move._prepare_move_line_vals(reserved_quant=lot_quant))
            ml['qty_done'] = 1
            rental_stock_move._action_done()

    def _return_serials(self, lot_ids, location_id, location_dest_id):
        """Undo the move of lot_ids from location_id to location_dest_id.

        :param stock.production.lot lot_ids:
        :param stock.location location_id:
        :param stock.location location_dest_id:
        """
        # VFE NOTE : or use stock moves to undo return/pickups ???
        if not lot_ids:
            return
        for lot_id in lot_ids:
            loc_id = lot_id.home_depot_id and lot_id.home_depot_id or location_id
            rental_stock_move = self.env['stock.move'].search([
                ('sale_line_id', '=', self.id),
                ('location_id', '=', location_id.id),
                ('location_dest_id', '=', loc_id.id)
            ])
            # rental_stock_move.write({'location_id': location_id.id,
            #     'location_dest_id': loc_id.id})
            for ml in rental_stock_move.mapped('move_line_ids'):
                # update move lines qties.
                if ml.lot_id.id == lot_id:
                    ml.qty_done = 0.0

            rental_stock_move.product_uom_qty -= 1

    #overwritten from sale rent module
    @api.depends('pickup_date')
    def _compute_reservation_begin(self):
        lines = self.filtered(lambda line: line.is_rental)
        for line in lines:
            if line.pickup_date:
                padding_timedelta_before = timedelta(hours=line.product_id.preparation_time)
                line.reservation_begin = line.pickup_date - padding_timedelta_before
            (self - lines).reservation_begin = None


    @api.model_create_multi
    def create(self, vals_list):           
        lines = super().create(vals_list)
        if lines.reserved_lot_ids:
            for line in lines:
                if line.reserved_lot_ids:
                    line.rental_reserved_lot_id = line.reserved_lot_ids[0].id
        return lines

    def write(self, values):
        if self.reserved_lot_ids:          
            values['rental_reserved_lot_id'] = self.reserved_lot_ids[0].id
        result = super(SaleOrderLine, self).write(values)
        return result

    def get_rental_order_line_description(self):
        if (self.is_rental):
            if self.pickup_date.date() == self.return_date.date():
                # If return day is the same as pickup day, don't display return_date Y/M/D in description.
                return_date = self.return_date
                if return_date:
                    return_date = return_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)
                return_date_part = format_time(self.with_context(use_babel=True).env, return_date, tz=self.env.user.tz, time_format=False)
            else:
                return_date_part = format_datetime(self.with_context(use_babel=True).env, self.return_date, tz=self.env.user.tz, dt_format=False)

            return "\n%s %s %s" % (
                format_datetime(self.with_context(use_babel=True).env, self.pickup_date, tz=self.env.user.tz, dt_format='').split(' ')[0],
                _("to"),
                return_date_part.split(' ')[0],
            )
        else:
            return ""

    def get_rental_order_date_description(self):
        import re
        for rec in  self:            
            if rec.return_date and rec.pickup_date:
                match = re.search(r'\d{2}/\d{2}/\d{4}', rec.name)
                _logger.info(str(rec.pickup_date))               
                if match:
                    date1 = datetime.strptime(match.group(), '%d/%m/%Y').date()                    
                    if date1:
                        date2= datetime.strftime(date1,'%d/%m/%Y')
                        pickup_date = format_datetime(self.with_context(use_babel=True).env, rec.pickup_date, tz=self.env.user.tz, dt_format=False)
                        pickup_date= datetime.strptime(pickup_date,'%d/%m/%Y %H:%M:%S').strftime('%d/%m/%Y')
                        _logger.info(str(date1)+" : "+ str(rec.pickup_date.date()))
                        _logger.info(str(pickup_date)+" : "+ str(rec.order_id.id))
                        name = rec.name.replace(date2, pickup_date)
                        _logger.info(str(name))
                        rec.write({'name' : name})
class ProductProduct(models.Model):
    _inherit = 'product.product'

    def get_product_multiline_description_sale(self):
        """Override method to pass only name of the product"""
        super(ProductProduct, self).get_product_multiline_description_sale()
        name = self.name
        if self.description_sale:
            name += '\n' + self.description_sale
        return name
