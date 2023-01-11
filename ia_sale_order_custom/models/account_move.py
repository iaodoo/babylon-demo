# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _
from datetime import datetime
from odoo.tools import float_compare, format_datetime, format_time
from pytz import timezone, UTC
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools.misc import formatLang, format_date, get_lang


class AccountMove(models.Model):
    _inherit = 'account.move'


    @api.constrains('payment_reference', 'move_type', 'partner_id', 'journal_id', 'invoice_date')
    def _check_duplicate_supplier_reference(self):
        moves = self.filtered(lambda move: move.is_purchase_document() and move.payment_reference)
        if not moves:
            return

        self.env["account.move"].flush([
            "payment_reference", "move_type", "invoice_date", "journal_id",
            "company_id", "partner_id", "commercial_partner_id",
        ])
        self.env["account.journal"].flush(["company_id"])
        self.env["res.partner"].flush(["commercial_partner_id"])

        # /!\ Computed stored fields are not yet inside the database.
        self._cr.execute('''
            SELECT move2.id
            FROM account_move move
            JOIN account_journal journal ON journal.id = move.journal_id
            JOIN res_partner partner ON partner.id = move.partner_id
            INNER JOIN account_move move2 ON
                move2.payment_reference = move.payment_reference
                AND move2.company_id = journal.company_id
                AND move2.commercial_partner_id = partner.commercial_partner_id
                AND move2.move_type = move.move_type
                AND (move.invoice_date is NULL OR move2.invoice_date = move.invoice_date)
                AND move2.id != move.id
            WHERE move.id IN %s
        ''', [tuple(moves.ids)])
        duplicated_moves = self.browse([r[0] for r in self._cr.fetchall()])
        if duplicated_moves:
            raise ValidationError(_('Duplicated vendor reference detected. You probably encoded twice the same vendor bill/credit note:\n%s') % "\n".join(
                duplicated_moves.mapped(lambda m: "%(partner)s - %(ref)s - %(date)s" % {
                    'ref': m.payment_reference,
                    'partner': m.partner_id.display_name,
                    'date': format_date(self.env, m.invoice_date),
                })
            ))

    is_rental_order_invoice = fields.Boolean("Created In App Rental", default=False)
    is_display_unit_price = fields.Boolean("Display Price Unit In Print", default=False)
    is_display_line_total = fields.Boolean("Display Line Total In Print", default=False)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('product_id')
    def _onchange_product_id_name(self):
        if self.product_id:
            if not self.move_id.is_rental_order_invoice:
                self.name = self.product_id.name

    @api.depends('pickup_date', 'return_date')
    def _compute_duration_days(self):
        for move in self:
            duration = 0
            if move.pickup_date and move.return_date:
                duration = (move.return_date - move.pickup_date).days + 1
            move.duration_days = int(duration)
            move.no_weeks = int(duration)/7

    duration_days = fields.Integer(string='Days', compute='_compute_duration_days')
    pickup_date = fields.Datetime(string="Pickup")
    return_date = fields.Datetime(string="Return")
    invoice_start_date = fields.Datetime(string="Invoice Start")
    invoice_end_date = fields.Datetime(string="Invoice End")
    order_number = fields.Char(string="Order Number")
    rental_reserved_lot_id = fields.Many2one('stock.production.lot',copy=False, string="Reseved Lot", help="Only available serial numbers are suggested.")
    rental_status = fields.Selection([
        ('draft', 'Quotation'),     
        ('picked', 'Picked-up'),
        ('returned', 'Returned'),
        ('cancel', 'Cancelled'),
    ], string="Rental Status", default="draft")
    daily_rate = fields.Float(string="Daily Rate")

    no_weeks = fields.Float(string='Weeks', compute='_compute_duration_days')
    weekly_rate = fields.Float(string="Weekly Rate")


    def get_rent_line_description(self):
        name = self.product_id.display_name
        name += self.get_rental_order_line_description()

    def get_rental_order_line_description(self):
        name = self.product_id.display_name if self.product_id else ""
        if self.pickup_date and self.return_date:
            if self.pickup_date.date() == self.return_date.date():
                # If return day is the same as pickup day, don't display return_date Y/M/D in description.
                return_date = self.return_date
                if return_date:
                    return_date = return_date.replace(tzinfo=UTC).astimezone(
                        timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)
                return_date_part = format_time(self.with_context(use_babel=True).env, return_date, tz=self.env.user.tz,
                                               time_format=False).split()[0]
            else:
                return_date_part = format_datetime(self.with_context(use_babel=True).env, self.return_date,
                                                   tz=self.env.user.tz, dt_format=False).split()[0]

            name += "\n%s %s %s %s" % (
                "Hire Period:",
                format_datetime(self.with_context(use_babel=True).env, self.pickup_date, tz=self.env.user.tz,
                                dt_format=False).split()[0],
                _("to"),
                return_date_part,
            )
        if self.mapped('sale_line_ids.reserved_lot_ids'):
            reserved_lot_names = self.mapped('sale_line_ids.reserved_lot_ids').mapped('name')
            name += "\n"
            name += ",".join(reserved_lot_names)
        return name
    ref = fields.Char(string='PO Number', copy=False, tracking=True)

