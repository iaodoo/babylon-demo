# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import base64
import requests
import json
from odoo.exceptions import ValidationError, Warning, UserError
from odoo import tools
import logging

_logger = logging.getLogger(__name__)


class Company(models.Model):
    _inherit = "res.company"

    payroll_business_id = fields.Char(
        string="Payroll Business ID",
        copy=False,
    )
    keypay_url = fields.Char(
        string="Payroll URL",
    )
    payroll_base_url = fields.Char(
        string="Payroll API URL",
    )
    api_key = fields.Char(
        string="API Key",
        default="S3lYOHVoaFZEeGZnSTlNMFA5YXd5QmorU0hoeVFNVzJiUmFNRzFNQjkxL0thMGQ1dFhnb1JNZklYUmJTR2h4Mw",
    )

    def check_connection(self):
        for record in self:
            company = record
            BaseURL = company.payroll_base_url
            BusinessID = company.payroll_business_id
            header = self.env['hr.employee']._prepare_header(company_id=company)
            if not BaseURL:
                _logger.info("Please set Payroll BaseURL in Company settings")
                return False
            if not BusinessID:
                _logger.info("Please set Payroll BusinessID in Company settings")
                return False
            WorkAPIUrl = "/business/%s" % (BusinessID)
            work_url = BaseURL + WorkAPIUrl
            response = requests.get(
                work_url,
                headers=header
            )
            if response.status_code == 200:
                raise ValidationError(_(str(response.status_code) + " : Keypay Connection is Successful"))
            else:
                raise ValidationError(_(str(response.status_code) + " : Please Verify Connection Parameters"))
