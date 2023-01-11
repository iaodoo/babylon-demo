# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
import logging

from psycopg2 import sql, DatabaseError

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import ValidationError, UserError
from odoo.addons.base.models.res_partner import WARNING_MESSAGE, WARNING_HELP

_logger = logging.getLogger(__name__)

# ---------------------------
# IN OUT Sheet
# ---------------------------
class InOutSheet(models.Model):
    _name = "ia.inout.sheet"
    _description = 'In / Out Sheet'
    _rec_name = 'sale_order_id'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']

    sale_order_id = fields.Many2one('sale.order', string='Sales Order')
    partner_id = fields.Many2one('res.partner', string='Company Receiving')
    site = fields.Char('Site')
    emp_name = fields.Char('Employee / Contractor Name')
    position = fields.Char('Position / Job Title')
    department = fields.Char('Department')
    lot_id = fields.Many2one('stock.production.lot', string='Fleet Number')
    comments = fields.Char('Comments')
    wta_signature = fields.Char('Westanks Representative')
    customer_signature = fields.Char('Customer Signature')
    off_hire_clean = fields.Selection([
        ('Yes', "Yes"),
        ('No', "No")], string ='Off Hire Cleaning?')
    off_hire_clean_charge = fields.Float('Cleaning Charges')
    state = fields.Selection([
        ('draft', "Waiting Hire Agreement"),
        ('out', "OUT Sheet"),
        ('outdone', "OUT Sheet Completed"),
        ('onhire', "IN Sheet"),
        ('in', "IN Sheet Completed"),
        ('hiredone', "Hire Completed")], default='draft', string="Status", tracking=1)
    out_safety_line = fields.One2many('out.safety.line', 'inout_id', string='Safety Features')
    out_operating_line = fields.One2many('out.operating.line', 'inout_id', string='Operating Functions')
    out_extra_line = fields.One2many('out.extra.line', 'inout_id', string='Extra Functions')
    in_trail_service_line_ids = fields.One2many('in.trail.service.line', 'inout_id', string='Trail Service')
    in_tank_service_line_ids = fields.One2many('in.tank.service.line', 'inout_id', string='Tank Service')
    in_comments = fields.Text('In Comments')

    ia_reserved_lot_ids = fields.Many2many('stock.production.lot', 'ia_rental_reserved_lot_relation', string = "Reserved Serial Numbers" , copy=True)


    ia_picked_lot_ids = fields.Many2many('stock.production.lot', 'ia_rental_picked_lot_relation', domain="[('id', 'in', ia_reserved_lot_ids)]", string = "Picked Serial Numbers" , copy=True)

    ia_returned_lot_ids = fields.Many2many('stock.production.lot', 'ia_rental_returned_lot_relation', domain="[('id', 'in', ia_reserved_lot_ids)]", string = "Retuned Serial Numbers" , copy=True)
    @api.model
    def default_get(self, fields_list):
        res = super(InOutSheet, self).default_get(fields_list)

        vals1 = []
        saf = self.env['out.safety.master'].search([])
        for each in saf:
            vals1.append((0, 0, {'feature_id': each.id, }))

        vals2 = []
        ops = self.env['out.operating.master'].search([])
        for each in ops:
            vals2.append((0, 0, {'feature_id': each.id, }))

        vals3 = []
        ext = self.env['out.extra.master'].search([])
        for each in ext:
            vals3.append((0, 0, {'feature_id': each.id, }))

        trail_ids = self.env['in.trail.service.master'].search([])
        trail_list = [(0, 0, {'feature_id': t.id, }) for t in trail_ids]

        tank_ids = self.env['in.tank.service.master'].search([])
        tank_list = [(0, 0, {'feature_id': t.id, }) for t in tank_ids]

        res.update({
            'out_safety_line': vals1,
            'out_operating_line': vals2,
            'out_extra_line': vals3,
            'in_trail_service_line_ids': trail_list,
            'in_tank_service_line_ids': tank_list
        })
        return res

    def button_duplicate(self):
        action = self.env["ir.actions.actions"]._for_xml_id("ia_crm_custom.ia_inout_sheet_action")
        for sheet in self:
            lot_ids = list(set(sheet.sale_order_id.in_out_sheets.ia_reserved_lot_ids.ids)-set(sheet.sale_order_id.in_out_sheets.ia_picked_lot_ids.ids))
            if not lot_ids:
               raise UserError(_('Please check pending serial numbers for outsheet creation'))
            sheet_id = sheet.copy({'ia_reserved_lot_ids':[(6,0,lot_ids)],'ia_picked_lot_ids':[(6,0,lot_ids)]})
            res = self.env.ref('ia_crm_custom.ia_inout_sheet_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = sheet_id.id
        return action



    def out_sheet(self):
        self.write({'state': 'out'})

    def copy(self, default = {}):
        if self.state == 'hiredone':
            default['state'] = 'onhire'
        else:
            default['state'] = self.state
        res = super(InOutSheet, self).copy(default)
        return res
    def out_sheetdone(self):

        # Temporarily Disable all checks for InOut Sheet
        
        # if not self.emp_name:
        #     raise ValidationError(_('Please enter Employee/Contractor Name'))
        # if not self.position:
        #     raise ValidationError(_('Please enter Position/Job Title'))
        # if not self.site:
        #     raise ValidationError(_('Please enter Site'))
        # if not self.department:
        #     raise ValidationError(_('Please enter Department'))
        # if not self.wta_signature:
        #     raise ValidationError(_('Please provide Westanks Represtative Signature'))
        # if not self.customer_signature:
        #     raise ValidationError(_('Please provide Customer Signature'))

        # if self.out_safety_line:
        #     for slines in self.out_safety_line:
        #         if not slines.explained_na:
        #             raise ValidationError(_('Please complete Safety Features section'))

        # if self.out_operating_line:
        #     for olines in self.out_operating_line:
        #         if not olines.explained_na:
        #             raise ValidationError(_('Please complete Operating Functions section'))

        # if self.out_extra_line:
        #     for elines in self.out_extra_line:
        #         if not elines.explained_na:
        #             raise ValidationError(_('Please complete Extra Functions section'))

        self.write({'state': 'outdone'})
        # self.state = 'outdone'
        # message_id = self.env['message.wizard'].create({'message': _("Out Sheet Confirmed. Please set the rental order to 'Picked Up'")})
      
        # return {
        #     'name': _('Successful'),
        #     'type': 'ir.actions.act_window',
        #     'view_mode': 'form',
        #     'res_model': 'message.wizard',
        #     # pass the id
        #     'res_id': message_id.id,
        #     'target': 'new'
        # }
    #	[WTA] Odoo Changes for In/Out Sheets (#8742)
    def pickup(self):
        if self.sale_order_id:
            return self.sale_order_id.open_pickup()
        else:
            return False
    #	[WTA] Odoo Changes for In/Out Sheets (#8742)
    def open_return(self):
        if self.sale_order_id:
            return self.sale_order_id.open_return()
        else:
            return False

    def onhire(self):
        self.write({'state': 'onhire'})
    
    def in_sheet(self):
        self.write({'state': 'in'})
    
    def done(self):
        self.write({'state': 'hiredone'})

# ---------------------------
# Safety Features
# ---------------------------
class OutSafetyLine(models.Model):
    _name = "out.safety.line"
    _description = "Safety Features"
    inout_id = fields.Many2one('ia.inout.sheet', string='In Out Sheet')
    feature_id = fields.Many2one('out.safety.master', string='Feature')
    explained = fields.Boolean('Explained')
    na = fields.Boolean('N/A')
    comments = fields.Char('Comments')
    explained_na = fields.Selection([
        ('explained', "Explained"),
        ('na', "NA")], string="Explained/Na")
    
    def button_explained(self):
        self.write({'explained_na': 'explained'})
    
    def button_na(self):
        self.write({'explained_na': 'na'})

class OutSafetyMaster(models.Model):
    _name = "out.safety.master"
    _description = "Safety master Features"

    name = fields.Char('Feature')

# ---------------------------
# Operating Functions
# ---------------------------
class OutOperatingLine(models.Model):
    _name = "out.operating.line"
    _description = "Operating Functions"

    inout_id = fields.Many2one('ia.inout.sheet', string='In Out Sheet')
    feature_id = fields.Many2one('out.operating.master', string='Feature')
    explained = fields.Boolean('Explained')
    na = fields.Boolean('N/A')
    comments = fields.Char('Comments')
    explained_na = fields.Selection([
        ('explained', "Explained"),
        ('na', "NA")], string="Explained/Na")
    
    def button_explained(self):
        self.write({'explained_na': 'explained'})
    
    def button_na(self):
        self.write({'explained_na': 'na'})

class OutOperatingMaster(models.Model):
    _name = "out.operating.master"
    _description = "Operating Functions Master"

    name = fields.Char('Feature')

# ---------------------------
# Extra Functions
# ---------------------------
class OutExtraLine(models.Model):
    _name = "out.extra.line"
    _description = "Extra Functions"

    inout_id = fields.Many2one('ia.inout.sheet', string='In Out Sheet')
    feature_id = fields.Many2one('out.extra.master', string='Feature')
    explained = fields.Boolean('Explained')
    na = fields.Boolean('N/A')
    comments = fields.Char('Comments')
    explained_na = fields.Selection([
        ('explained', "Explained"),
        ('na', "NA")], string="Explained/Na")
    
    def button_explained(self):
        self.write({'explained_na': 'explained'})
    
    def button_na(self):
        self.write({'explained_na': 'na'})

class OutExtraMaster(models.Model):
    _name = "out.extra.master"
    _description = "Extra Functions Master"
    name = fields.Char('Feature')


# ---------------------------
# Trail Service
# ---------------------------
class InTrailServiceLine(models.Model):
    _name = "in.trail.service.line"
    _description = "Trail Service"
    inout_id = fields.Many2one('ia.inout.sheet', string='In Out Sheet')
    feature_id = fields.Many2one('in.trail.service.master', string='Feature')
    explained = fields.Boolean('Explained')
    na = fields.Boolean('N/A')
    comments = fields.Char('Comments')
    explained_na = fields.Selection([
        ('explained', "Functioning"),
        ('na', "Repairs Required")], string="Functioning")

    def button_explained(self):
        self.write({'explained_na': 'explained'})

    def button_na(self):
        self.write({'explained_na': 'na'})


class InTrailServiceMaster(models.Model):
    _name = "in.trail.service.master"
    _description = "Trail Service Master"
    name = fields.Char('Feature')


# ---------------------------
# Tank Service
# ---------------------------
class InTankServiceLine(models.Model):
    _name = "in.tank.service.line"
    _description = "Tank Service"
    inout_id = fields.Many2one('ia.inout.sheet', string='In Out Sheet')
    feature_id = fields.Many2one('in.tank.service.master', string='Feature')
    explained = fields.Boolean('Explained')
    na = fields.Boolean('N/A')
    comments = fields.Char('Comments')
    explained_na = fields.Selection([
        ('explained', "Functioning"),
        ('na', "Repairs Required")], string="Functioning")

    def button_explained(self):
        self.write({'explained_na': 'explained'})

    def button_na(self):
        self.write({'explained_na': 'na'})


class InTankServiceMaster(models.Model):
    _name = "in.tank.service.master"
    _description = "Tank Service master"
    name = fields.Char('Feature')


class MessageWizard(models.TransientModel):
    _name = 'message.wizard'
    _description = 'For Message'
    message = fields.Text(string="Message", readonly=True)    
    def action_ok(self):
        """ close wizard"""       
        return {'type': 'ir.actions.act_window_close'}

