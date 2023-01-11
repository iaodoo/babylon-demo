# -*- coding: utf-8 -*-
import base64
import requests
import json

from odoo import models, fields, api


class AccountAnalyticTag(models.Model):
    _inherit = 'account.analytic.tag'

    kp_analytic_tag_identifier = fields.Integer('Keypay location id',
                                                    help="Identifier of the keypay location that created this account")

    def _create_keypay_location(self, name):
        self.ensure_one()
        company = self.env.user.company_id
        BaseURL = company.payroll_base_url
        BusinessID = company.payroll_business_id
        header = self.env['hr.employee']._prepare_header()
        LocUrl = "/business/%s/location" % BusinessID
        kp_analytic_tag_identifier = 0
        if not BaseURL:
            return kp_analytic_tag_identifier
        url = BaseURL + LocUrl
        data = {
            "name": name or '',
            "externalId": name or '',
            "source": "None",
            "fullyQualifiedName": name or '',
            "isGlobal": True,
            "isRollupReportingLocation": False,
            "defaultShiftConditionIds": [],
        }
        response = requests.post(url, headers=header, data=json.dumps(data))
        response.raise_for_status()
        if response.status_code in (200, 201, 202):
            location = response.json()
            kp_analytic_tag_identifier = location.get('id', 0)
        return kp_analytic_tag_identifier

    def _delete_keypay_location(self):
        self.ensure_one()
        company = self.env.user.company_id
        BaseURL = company.payroll_base_url
        BusinessID = company.payroll_business_id
        header = self.env['hr.employee']._prepare_header()
        LocUrl = "/business/%s/location/%s" % (BusinessID, str(self.kp_analytic_tag_identifier))
        if not BaseURL:
            return False
        url = BaseURL + LocUrl
        response = requests.delete(url, headers=header)
        response.raise_for_status()
        if response.status_code in (200, 201, 202):
            return True
        return False

    @api.model
    def create(self, vals):
        res = super(AccountAnalyticTag, self).create(vals)
        kp_analytic_tag_identifier = res._create_keypay_location(vals['name'])
        res.write({'kp_analytic_tag_identifier': kp_analytic_tag_identifier})
        return res

    def write(self, vals):
        for record in self:
            if 'active' in vals and not vals['active']:
                if record.kp_analytic_tag_identifier:
                    if record._delete_keypay_location():
                        vals['kp_analytic_tag_identifier'] = 0
            if 'active' in vals and vals['active']:
                if not record.kp_analytic_tag_identifier:
                    vals['kp_analytic_tag_identifier'] = record._create_keypay_location(record.name)
        super(AccountAnalyticTag, self).write(vals)
