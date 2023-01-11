import re
import time
import logging
import pytz
from psycopg2 import sql, DatabaseError

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import ValidationError
from odoo.addons.base.models.res_partner import WARNING_MESSAGE, WARNING_HELP
from datetime import date, timedelta, datetime
import calendar
from odoo.tools import float_compare, format_datetime, format_time
from pytz import timezone, UTC
from dateutil.relativedelta import relativedelta


class RentalWizard(models.TransientModel):
    _inherit = 'rental.wizard'
    rental_lot_id = fields.Many2one('stock.production.lot', string="Serial Number", help="Only available serial numbers are suggested.",
                                    domain="[(qty_available_during_period > 0, '=', 1), ('id', 'not in', rented_lot_ids), ('id', 'in', rentable_lot_ids)]")

    unit_price = fields.Float(
        string="Unit Price", help="This price is based on the rental price rule that gives the cheapest price for requested duration.",
        readonly=False, default=0.0, required=True, digits=(16,4))

    @api.onchange('rental_lot_id')
    def _rental_lot_id(self):
        if self.rental_lot_id:
            # if  self.rental_lot_id.rental_status != 'returned':
            #     if self.rental_lot_id.rental_status:
            #         raise ValidationError(_("No valid quant has been found  for serial number %s !") % (self.rental_lot_id.name))
            self.lot_ids = [(6, 0, [self.rental_lot_id.id])]

    @api.onchange('lot_ids')
    def _rental_lot_ids(self):
        if self.lot_ids:
            self.rental_lot_id = self.lot_ids.ids[0]

    @api.onchange('pickup_date')
    def _rental_pickup_date(self):
        if self.pickup_date:  
            pickup_date = self.pickup_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)
            # time_timezone = format_time(self.with_context(use_babel=True).env, pickup_date, tz=self.env.user.tz, time_format=False)
            # time_timezone = time_timezone.split(':')
            # pickup_date = datetime.combine(self.pickup_date, datetime.min.time())
            # pickup_date = pickup_date - timedelta(hours=int(time_timezone[0]),minutes = int(time_timezone[1]))         
            # self.pickup_date = pickup_date
            pickup_date = datetime.combine(pickup_date, datetime.min.time())
            user_date = datetime.now(pytz.timezone(self.env.user.tz or 'UTC'))
            utc_diff = user_date.utcoffset().total_seconds()/60/60
            self.pickup_date = pickup_date - timedelta(hours=utc_diff)
    
    @api.onchange('return_date')
    def _rental_return_date(self):
        if self.return_date: 
            return_date = self.return_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)
            # time_timezone = format_time(self.with_context(use_babel=True).env, return_date, tz=self.env.user.tz, time_format=False)
            # time_timezone = time_timezone.split(':')
            # return_date = datetime.combine(self.return_date, datetime.max.time())      
            # return_date = return_date - timedelta(hours=int(time_timezone[0]),minutes = int(time_timezone[1]))
            # self.return_date = return_date
            return_date = datetime.combine(return_date, datetime.max.time())     
            user_date = datetime.now(pytz.timezone(self.env.user.tz or 'UTC'))
            utc_diff = user_date.utcoffset().total_seconds()/60/60
            self.return_date = return_date - timedelta(hours=utc_diff)
    
