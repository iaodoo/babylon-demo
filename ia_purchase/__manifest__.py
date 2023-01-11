# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Purchase Customization',
    'version': '14.0.1',
    'author': 'Ioppolo & Associates',
    'category': 'purchase',
    'summary': 'Purchase Customization',
    'description': """
              Purchase Customization
    """,
    'depends': ['purchase'],
    'data': [
        'views/purchase_view.xml',
        'report/purchase_order_rep.xml',
        ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'auto_install': False
}
