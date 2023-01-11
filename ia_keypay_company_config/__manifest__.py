# -*- coding: utf-8 -*-
##############################################################################
#    Copyright (C) Ioppolo and Associates (I&A) 2020 (<http://ioppolo.com.au>).
###############################################################################

{
    "name": "I&A Keypay Payroll - Company Configuration",
    "version": "14.0",
    "depends": [
        "base",
        'hr',
    ],
    "category": "Ioppolo & Associates",
    "author": "Ioppolo & Associates",
    "website": "http://www.ioppolo.com.au/",
    "summary": "I&A Keypay Payroll - Company Configuration",
    "description": """
                I&A Keypay Payroll
                Odoo Keypay API Configuration 
                Employee Synch from Odoo to Keypay
    """,
    'data': [
        'data/base_automation.xml',
        'data/pay_schedule_data.xml',
        'views/res_company_view.xml',
        'views/payroll_components.xml',
        'security/ir.model.access.csv',
    ],
    "installable": True,
}
