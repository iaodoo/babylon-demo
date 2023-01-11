# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Tank Builder',
    'version': '14.1',
    'author': 'Ioppolo & Associates',
    'category': 'crm',
    'summary': 'SOW 2.0: Tank Builder (Quote / SO) Input',
    'description': """
             Customise quotation screen to mirror Tank Builder Spreadsheet. 
             Tank Builder will be visible to Odoo users only, not client.
              Client will only see PDF Output. Automate 'Cost' Field based on 
              Vendor Pricelists. Purchase Module Required. Adjustable Markup Value.
    """,
    'depends': ['sale_stock_renting', 'account_followup', 'ia_crm_custom', 'base_automation'],
    'data': [
        'data/base_automation.xml',
        'data/report_paperformat_data.xml',
        'views/sale_order_view.xml',
        'views/res_config_settings_views.xml',
        'report/rental_schedule.xml',  
        'wizard/sale_rental_invoice_views.xml',
        'security/ir.model.access.csv',
        'views/report_followup.xml',
        'views/rental_configurator_views.xml',
        'views/account_move.xml',
        'views/mail_template_data.xml',
        'views/report_payment_receipt_templates.xml',
        ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'auto_install': False
}
