# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import base64

_logger = logging.getLogger(__name__)


# ===================================
#  Employment Type
# ===================================
class EmploymentType(models.Model):
    _name = 'employment.type'
    _description = 'Employment Type'
    _rec_name = 'name'

    name = fields.Char(
        string='Name',
        required=True,
    )
    synch = fields.Boolean(
        string='Synch with Payroll'
    )
    active = fields.Boolean(
        string='Active', default=True
    )

    def unlink(self):
        for emptype in self:
            raise UserError(_("You cannot delete an record which has been created once."))
        return super(EmploymentType, self).unlink()


# ===================================
#  Employee Pay Schedule
# ===================================
class IaEmployeePaySchedule(models.Model):
    _name = 'ia.employee.pay.schedule'
    _description = 'Employee Pay Schedule'
    _rec_name = 'name'
    name = fields.Char(
        string='Name',
        required=True,
    )
    synch = fields.Boolean(
        string='Synch with Payroll'
    )
    active = fields.Boolean(
        string='Active', default=True
    )

    def unlink(self):
        for schedule in self:
            raise UserError(_("You cannot delete an record which has been created once."))
        return super(IaEmployeePaySchedule, self).unlink()


# #Class: Hr.employee
class HrEmployee(models.Model):
    _inherit = "hr.employee"
    payroll_employee_id = fields.Char("Employee ID", readonly=False, copy=False, tracking=True)
    # Work Type
    emp_type_id = fields.Many2one('employment.type', 'Employment Type')
    pay_schedule_id = fields.Many2one('ia.employee.pay.schedule', string='Pay Schedule', tracking=True, copy=False)

    # Class: Hr.employee
    @api.model
    def _prepare_header(self, employee=False, company_id=False):
        user = self.env.user
        company = employee and employee.company_id or False
        company = (not company and company_id) and company_id or self.env.user.company_id
        APIKey = company.api_key
        if not APIKey:
            _logger.info("Employee doesn't synchronized due to APIKey for employee not set")
            return False

        # Generate authentication key
        authstr2 = base64.b64encode(APIKey.encode())
        authstr = "Basic " + authstr2.decode("utf-8")

        headers = {
            "Authorization": authstr,
            "Content-Type": "application/json",
            "Accept": "text/plain"
        }
        return headers
