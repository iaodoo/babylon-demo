# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from decimal import InvalidOperation
from re import U
import time

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import calendar
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
from odoo.tools import float_compare, format_datetime, format_time
from pytz import timezone, UTC
class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"
    @api.model
    def default_get(self, fields):
        res = super(SaleAdvancePaymentInv, self).default_get(fields)
        if self._context.get('active_model') == 'sale.order' and self._context.get('active_ids', False):
            sale_order = self.env['sale.order'].browse(self._context.get('active_ids'))
            order =  sale_order.filtered(
                lambda sale_order: sale_order.is_rental_order
            )
            if order:
                res['deduct_down_payments'] = False
                #raise UserError(_("This option is not available for rental orders")) 
        return res
class SaleRentalInv(models.TransientModel):
    _name = "sale.rental.inv"
    _description = "Sales Rental Invoice"
    
    invoice_date = fields.Date(string='Invoice Date')   

    def create_invoices(self):
        start_day_of_month = self.invoice_date.replace(day=1)                 
        year, month = self.invoice_date.year,self.invoice_date.month
        last_day = calendar.monthrange(year, month)[1]
        end_day_of_month = self.invoice_date.replace(day=last_day)
        start_day_of_month = datetime.combine(start_day_of_month, datetime.min.time())
        end_day_of_month = datetime.combine(end_day_of_month, datetime.max.time())
        start_day_of_month1 = start_day_of_month.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)
        time_timezone = format_time(self.with_context(use_babel=True).env, start_day_of_month1, tz=self.env.user.tz, time_format=False)
        time_timezone = time_timezone.split(':')
        start_day_of_month = start_day_of_month - timedelta(hours=int(time_timezone[0]),minutes = int(time_timezone[1]))
        end_day_of_month = end_day_of_month - timedelta(hours=int(time_timezone[0]),minutes = int(time_timezone[1]))
        # sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
        sale_orders_list = []
        sale_order_lines = self.env['sale.order.line'].search([('order_id','in', self._context.get('active_ids', []))]).filtered(lambda line: (line.product_id.invoice_monthly == True and line.pickup_date 
                    and line.return_date and  line.order_id.rental_status) and line.rental_status in ('picked','returned') and ((line.pickup_date >= start_day_of_month and line.return_date <= end_day_of_month) or 
                    (line.pickup_date < start_day_of_month and line.return_date <= end_day_of_month) or
                    (line.pickup_date >= start_day_of_month and line.return_date > end_day_of_month)  or
                    (line.pickup_date < start_day_of_month and line.return_date > end_day_of_month)))
        # for saleorder in sale_orders:
        #     for line in saleorder.order_line:
        #         if (line.product_id.invoice_monthly == True and line.pickup_date 
        #             and line.return_date and  line.order_id.rental_status) and line.order_id.rental_status in ('return','returned') and ((line.pickup_date >= start_day_of_month and line.return_date <= end_day_of_month) or 
        #             (line.pickup_date < start_day_of_month and line.return_date <= end_day_of_month) or
        #             (line.pickup_date >= start_day_of_month and line.return_date > end_day_of_month)  or
        #             (line.pickup_date < start_day_of_month and line.return_date > end_day_of_month)):
        #             sale_orders_list.append(saleorder.id)
        #             break
                
        #sale_orders = self.env['sale.order'].browse(sale_orders_list)
        if sale_order_lines:
            order_id = False
            invoice_vals = {}
            invoice_ids = []
            origin = False
            for order_line in sale_order_lines.sorted(lambda x: x.order_id):
                if order_line.rental_status == 'returned' and order_line.return_date < start_day_of_month:
                    continue
                move_line = self.env['account.move.line'].search([('sale_line_ids','in',order_line.ids),('move_id.invoice_date','=',self.invoice_date),('move_id.state','!=','cancel')])
                if move_line:
                    continue
                if order_id != order_line.order_id.id: 
                    if  invoice_vals:                              
                        invoice = self.env['account.move'].with_company(order_line.order_id.company_id)\
                        .sudo().create(invoice_vals).with_user(self.env.uid)
                        invoice_ids.append(invoice.id)
                        invoice.message_post_with_view('mail.message_origin_link',
                                values={'self': invoice, 'origin': origin},
                                subtype_id=self.env.ref('mail.mt_note').id)
                    invoice_vals = self._prepare_invoice_values(order_line.order_id)
                    invoice_vals['invoice_line_ids'] = []
                    order_id = order_line.order_id.id  
                invoice_line_values = self._prepare_invoice_line_values(order_line)    
                invoice_vals['invoice_line_ids'].append((0, 0, invoice_line_values))
                origin = order_line.order_id
            if  invoice_vals:                              
                invoice = self.env['account.move'].with_company(origin.company_id)\
                .sudo().create(invoice_vals).with_user(self.env.uid)
                invoice_ids.append(invoice.id)
                invoice.message_post_with_view('mail.message_origin_link',
                        values={'self': invoice, 'origin': origin},
                        subtype_id=self.env.ref('mail.mt_note').id)
    
        else:
            # saleorders = self.env['sale.order'].browse(self._context.get('active_ids', []))
            # for saleorder in saleorders:
            #     for orderline in saleorder.order_line:
            raise UserError(_("Please check the rental status of selected orders."))       
        if self._context.get('open_invoices', False) and len(invoice_ids) > 0:
           # invoices = self.mapped('invoice_ids')
            action = self.env["ir.actions.actions"]._for_xml_id(
                "ia_sale_order_custom.action_account_moves_journal_rentals")
            action['domain'] = [('exclude_from_invoice_tab', '=', False),('move_id', 'in', invoice_ids)]
            return action
        return {'type': 'ir.actions.act_window_close'}

   
    def _prepare_invoice_values(self, order):
        invoice_vals = {
            'ref': order.client_order_ref,
            'move_type': 'out_invoice',
            'invoice_origin': order.name,
            'invoice_user_id': order.user_id.id,
            'narration': order.note,
            'partner_id': order.partner_invoice_id.id,
            'fiscal_position_id': (order.fiscal_position_id or order.fiscal_position_id.get_fiscal_position(order.partner_id.id)).id,
            'partner_shipping_id': order.partner_shipping_id.id,
            'currency_id': order.pricelist_id.currency_id.id,
            'payment_reference': order.reference,
            'invoice_payment_term_id': order.payment_term_id.id,
            'partner_bank_id': order.company_id.partner_id.bank_ids[:1].id,
            'team_id': order.team_id.id,
            'campaign_id': order.campaign_id.id,
            'medium_id': order.medium_id.id,
            'source_id': order.source_id.id,
            'invoice_date' : self.invoice_date,
            'is_rental_order_invoice': order.is_rental_order,
            'site_location' : order.site_location,

        }
        if order.is_rental_order:
            invoice_vals['narration'] = order.company_id.with_context(
                lang=order.partner_id.lang or order.env.lang).rental_invoice_terms
        
        return invoice_vals
    def _prepare_invoice_line_values(self, line):
        invoice_line_vals = {}
       # invoice_vals['invoice_line_ids'] = []
        start_day_of_month = self.invoice_date.replace(day=1)                 
        year, month = self.invoice_date.year,self.invoice_date.month
        last_day = calendar.monthrange(year, month)[1]
        end_day_of_month = self.invoice_date.replace(day=last_day)          
        start_day_of_month = datetime.combine(start_day_of_month, datetime.min.time())
        end_day_of_month = datetime.combine(end_day_of_month, datetime.max.time())

        end_return_day_of_month = end_day_of_month+ relativedelta(months=1)
        year, month = end_return_day_of_month.year,end_return_day_of_month.month
        last_day = calendar.monthrange(year, month)[1]
        end_return_day_of_month = end_return_day_of_month.replace(day=last_day) 
         



        price_unit = 0.0
        pickup_date = line.pickup_date
        return_date = line.return_date
        name = ''
        start_day_of_month1 = start_day_of_month.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)
        # end_day_of_month = end_day_of_month.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)
        time_timezone = format_time(self.with_context(use_babel=True).env, start_day_of_month1, tz=self.env.user.tz, time_format=False)
        time_timezone = time_timezone.split(':')
        start_day_of_month = start_day_of_month - timedelta(hours=int(time_timezone[0]),minutes = int(time_timezone[1]))
        end_day_of_month = end_day_of_month - timedelta(hours=int(time_timezone[0]),minutes = int(time_timezone[1]))

        end_return_day_of_month = end_return_day_of_month - timedelta(hours=int(time_timezone[0]),minutes = int(time_timezone[1]))
        if line.pickup_date >= start_day_of_month and line.return_date <= end_day_of_month:
            if line.rental_status == 'returned':
                price_unit = self._compute_unit_price_rental_inv(line,line.pickup_date, line.return_date) 
                name = line.product_id.get_product_multiline_description_sale() + line._get_sale_order_line_multiline_description_variants()+ self.get_rental_invoice_line_description(line,line.pickup_date, line.return_date)
            elif line.rental_status == 'picked':                      
                price_unit =   self._compute_unit_price_rental_inv(line,line.pickup_date, end_day_of_month) 
                line.write({'return_date' : end_return_day_of_month})                   
                name =   line.product_id.get_product_multiline_description_sale() + line._get_sale_order_line_multiline_description_variants()+ self.get_rental_invoice_line_description(line, line.pickup_date, end_day_of_month)
                return_date = end_day_of_month
                
        if (line.pickup_date < start_day_of_month and line.return_date <= end_day_of_month):
            if line.rental_status == 'returned':                 
                price_unit = self._compute_unit_price_rental_inv(line, start_day_of_month, line.return_date)                      
                name =  line.product_id.get_product_multiline_description_sale() + line._get_sale_order_line_multiline_description_variants()+ self.get_rental_invoice_line_description(line, start_day_of_month, line.return_date)
                pickup_date = start_day_of_month
            elif line.rental_status == 'picked':
                price_unit =   self._compute_unit_price_rental_inv(line,start_day_of_month, end_day_of_month) 
                line.write({'return_date' : end_return_day_of_month})
                name =   line.product_id.get_product_multiline_description_sale() + line._get_sale_order_line_multiline_description_variants()+ self.get_rental_invoice_line_description(line, start_day_of_month, end_day_of_month)
            
                pickup_date = start_day_of_month
                return_date = end_day_of_month
        if (line.pickup_date >= start_day_of_month and line.return_date > end_day_of_month):  
            if line.rental_status == 'picked':                  
                price_unit = self._compute_unit_price_rental_inv(line,line.pickup_date, end_day_of_month)         
                name =  line.product_id.get_product_multiline_description_sale() + line._get_sale_order_line_multiline_description_variants()+ self.get_rental_invoice_line_description(line, line.pickup_date, end_day_of_month)
                return_date = end_day_of_month

        if (line.pickup_date < start_day_of_month and line.return_date > end_day_of_month):
            if line.rental_status == 'picked':                    
                price_unit = self._compute_unit_price_rental_inv(line,start_day_of_month, end_day_of_month)                    
                name =  line.product_id.get_product_multiline_description_sale() + line._get_sale_order_line_multiline_description_variants()+ self.get_rental_invoice_line_description(line, start_day_of_month, end_day_of_month)
                pickup_date = start_day_of_month
                return_date = end_day_of_month
                # if (line.return_date <= end_day_of_month and order.rental_status and order.rental_status=='return'):
                #     line.write({'return_date' : end_day_of_month+ relativedelta(months=1)})

            # elif (line.return_date <= end_day_of_month and order.rental_status and order.rental_status=='return'):
            #     if (line.pickup_date >= start_day_of_month):
            #         duration_dict = self.env['rental.pricing']._compute_duration_vals(line.pickup_date, end_day_of_month)
            #         price_unit =   self._compute_unit_price_rental_inv(line,line.pickup_date, end_day_of_month, duration_dict['week'] ) 
            #         name =   line.product_id.get_product_multiline_description_sale() + line._get_sale_order_line_multiline_description_variants()+ self.get_rental_invoice_line_description(line, line.pickup_date, end_day_of_month)
            #         line.write({'return_date' : end_day_of_month+ relativedelta(months=1)})
            #     elif(line.pickup_date < start_day_of_month):
            #         duration_dict = self.env['rental.pricing']._compute_duration_vals(start_day_of_month, end_day_of_month)
            #         price_unit =   self._compute_unit_price_rental_inv(line,start_day_of_month, end_day_of_month, duration_dict['week'] ) 
            #         name =   line.product_id.get_product_multiline_description_sale() + line._get_sale_order_line_multiline_description_variants()+ self.get_rental_invoice_line_description(line, start_day_of_month, end_day_of_month)
            #         line.write({'return_date' : end_day_of_month+ relativedelta(months=1)})
        if (line.pickup_date >= start_day_of_month and line.return_date >= end_day_of_month):
            if line.rental_status == 'picked':
                price_unit =   self._compute_unit_price_rental_inv(line, pickup_date, end_day_of_month) 
                line.write({'return_date' : end_return_day_of_month})
                name =   line.product_id.get_product_multiline_description_sale() + line._get_sale_order_line_multiline_description_variants()+ self.get_rental_invoice_line_description(line, start_day_of_month, end_day_of_month)
                return_date = end_day_of_month
                

        invoice_line_vals = {
            'name': name,
            'price_unit': price_unit,
            'quantity': line.product_uom_qty,
            'product_id': line.product_id.id,
            'product_uom_id': line.product_uom.id,
            'tax_ids': [(6, 0, line.tax_id.ids)],
            'sale_line_ids': [(6, 0, [line.id])],
            'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
            'analytic_account_id': line.order_id.analytic_account_id.id or False,
            'pickup_date': pickup_date,
            'return_date': return_date,
            'invoice_start_date': pickup_date,
            'invoice_end_date': return_date,
            'order_number':line.order_id.name,
            'rental_reserved_lot_id':line.rental_reserved_lot_id.id,
            'rental_status':line.rental_status,
            'daily_rate':line.daily_rate,
            #'no_weeks': line.rental_duration,
            'weekly_rate': line.weekly_rate,
            'hide_days': line.product_id.hide_days
        }
        return invoice_line_vals
          

    def _compute_unit_price_rental_inv(self, line, pickup_date, return_date):       
            unit_price = 0.0
            if line.rental_duration > 0:
                if pickup_date and return_date:
                    pricing_id = line.product_id._get_best_pricing_rule(
                        pickup_date=pickup_date,
                        return_date=return_date,
                        pricelist=line.order_id.pricelist_id,
                        company=line.order_id.company_id)
                    if not pricing_id:
                        raise UserError('Pricelist on product "'+str(line.product_id.name)+'" does not match pricelist on order "'+str(line.order_id.name)+'"')
                    duration_dict = self.env['rental.pricing']._compute_duration_vals(pickup_date, return_date)
                    rental_duration = duration_dict[pricing_id.unit]
                    if pricing_id:
                        unit_price = pricing_id._compute_price(int(rental_duration), pricing_id.unit)
                        if line.order_id.currency_id != pricing_id.currency_id:
                            line.unit_price = pricing_id.currency_id._convert(
                                from_amount=unit_price,
                                to_currency=line.order_id.currency_id,
                                company=line.order_id.company_id,
                                date=self.invoice_date)
                        else:
                            unit_price = unit_price
                    elif rental_duration > 0:
                        unit_price = line.product_id.lst_price  
            return unit_price   
    
    def get_rental_invoice_line_description(self, line,  pickup_date, return_date):
        if (line.is_rental):
            if pickup_date.date() == return_date.date():
                # If return day is the same as pickup day, don't display return_date Y/M/D in description.
                return_date = return_date
                if return_date:
                    return_date = return_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)
                return_date_part = format_time(self.with_context(use_babel=True).env, return_date, tz=self.env.user.tz, time_format=False)
            else:
                return_date_part = format_datetime(self.with_context(use_babel=True).env, return_date, tz=self.env.user.tz, dt_format=False)

            return "\n%s %s %s" % (
                format_datetime(self.with_context(use_babel=True).env, pickup_date, tz=self.env.user.tz, dt_format=False),
                _("to"),
                return_date_part,
            )
        else:
            return ""
