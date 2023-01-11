# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sales Order Customization',
    'version': '1.1',
    'author': 'Ioppolo & Associates',
    'category': 'sale',
    'summary': 'Sales Order Customization',
    'description': """
              Add Product Images to Quotation / Sales Order Report
    """,
    'depends': ['ia_sale_order_custom'],
    'data': [
        'data/report_paperformat.xml',
        'data/mail_template_data.xml',
        'report/rental_invoice_view.xml',
        'report/sale_order_report.xml',
        'report/invoice_report.xml',
        'report/sale_cover_letter.xml',
        'views/report_header_view.xml',
    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'auto_install': False
}
