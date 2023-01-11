# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'CRM and Sale Customization',
    'version': '14.0.1',
    'author': 'Ioppolo & Associates',
    'category': 'crm',
    'summary': 'CRM and Sale Customization',
    'description': """
              CRM and Sale Customization
    """,
    'depends': ['crm', 'sale', 'sale_crm', 'stock', 'account' , 'base', 'project'
                ],
    'data': [
        'security/ir.model.access.csv',
        'views/crm_view.xml',
        'views/sale_view.xml',
        'views/mail_template_data.xml',
        'views/in_out_sheet.xml',
        'views/stock_view.xml',
        'views/invoice_view.xml',
        'data/data.xml',
        ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'auto_install': False
}
