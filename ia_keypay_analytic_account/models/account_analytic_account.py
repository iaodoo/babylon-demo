# -*- coding: utf-8 -*-
import base64
import requests
import json
import logging
from datetime import datetime

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    kp_analytic_account_identifier = fields.Integer('Keypay worktype id',
                                                    help="Identifier of the keypay worktype that created this account")

    def _cron_auto_create_keypay_worktype(self):
        cron_start_date = datetime.now()
        analytic_accounts = self.env['account.analytic.account'].search([('kp_analytic_account_identifier', '=', False)])
        for analytic_account in analytic_accounts:
            kp_analytic_account_identifier = analytic_account._create_keypay_worktype(analytic_account.name)
            analytic_account.write({'kp_analytic_account_identifier': kp_analytic_account_identifier})
        _logger.info("Key Pay WorkType Creation : Cron duration = %d seconds" % (
            (datetime.now() - cron_start_date).total_seconds()))

    def _create_keypay_worktype(self, name):
        self.ensure_one()
        company = self.env.user.company_id
        BaseURL = company.payroll_base_url
        BusinessID = company.payroll_business_id
        header = self.env['hr.employee']._prepare_header()
        LocUrl = "/business/%s/worktype" % BusinessID
        kp_analytic_account_identifier = 0
        if not BaseURL:
            return kp_analytic_account_identifier
        url = BaseURL + LocUrl
        data = {
            "employmentTypes": [
                "FullTime",
                "PartTime",
                "LabourHire",
                "SuperannuationIncomeStream",
                "Casual"
            ],
            "name": name or '',
            "externalId": name or '',
            "source": "None",
            "mappingType": "PrimaryPayCategory",
        }
        response = requests.post(url, headers=header, data=json.dumps(data))
        response.raise_for_status()
        if response.status_code in (200, 201, 202):
            work_type = response.json()
            kp_analytic_account_identifier = work_type.get('id', 0)
        return kp_analytic_account_identifier

    def _delete_keypay_worktype(self):
        self.ensure_one()
        company = self.env.user.company_id
        BaseURL = company.payroll_base_url
        BusinessID = company.payroll_business_id
        header = self.env['hr.employee']._prepare_header()
        LocUrl = "/business/%s/worktype/%s" % (BusinessID, str(self.kp_analytic_account_identifier))
        if not BaseURL:
            return False
        url = BaseURL + LocUrl
        response = requests.delete(url, headers=header)
        response.raise_for_status()
        if response.status_code in (200, 201, 202):
            return True
        return False

    def write(self, vals):
        for record in self:
            if 'active' in vals and not vals['active']:
                if record.kp_analytic_account_identifier:
                    if record._delete_keypay_worktype():
                        vals['kp_analytic_account_identifier'] = 0
            if 'active' in vals and vals['active']:
                if not record.kp_analytic_account_identifier:
                    vals['kp_analytic_account_identifier'] = record._create_keypay_worktype(record.name)
        super(AccountAnalyticAccount, self).write(vals)
