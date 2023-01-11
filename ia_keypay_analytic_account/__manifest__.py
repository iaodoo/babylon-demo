# -*- coding: utf-8 -*-
##############################################################################
#    Copyright (C) Ioppolo and Associates (I&A) 2020 (<http://ioppolo.com.au>).
###############################################################################

{
    "name": "I&A Keypay Payroll - Analytic",
    "version": "14.0",
    "depends": [
        "ia_keypay_company_config",
        "analytic",
    ],
    "category": "Ioppolo & Associates",
    "author": "Ioppolo & Associates",
    "website": "http://www.ioppolo.com.au/",
    "summary": "I&A Keypay Payroll - Analytic",
    "description": """
                I&A Keypay Payroll
    """,
    'data': [
        'data/ir_cron_data.xml',
        'views/analytic_views.xml',
    ],
    "installable": True,
}
