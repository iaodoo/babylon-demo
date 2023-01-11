# -*- coding: utf-8 -*-

##############################################################################
#    Copyright (C) Ioppolo and Associates (I&A) 2020 (<http://ioppolo.com.au>).
###############################################################################


{
    "name": "Limit Account Analytic Creation",
    "version": "14.0",
    "depends": [
        "account",
        "sale",
        "purchase",
    ],
    "category": "Ioppolo & Associates",
    "author": "Ioppolo & Associates",
    "website": "http://www.ioppolo.com.au/",
    "summary": "Account Analytic Customisation",
    "description": """Account Analytic Customisation 
    1. Remove all Quick Creation of Analytic Account and Tag in Sale, Purchase, Account related modules.
    """,
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/account.xml',
        'views/sale.xml',
        'views/purchase.xml',
    ],
    "installable": True,
}
