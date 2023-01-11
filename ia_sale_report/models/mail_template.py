# -*- coding: utf-8 -*-
import base64

from odoo import api, models


class MailTemplate(models.Model):
    _inherit = "mail.template"

    def generate_email(self, res_ids, fields):
        result = super().generate_email(res_ids, fields)
        if self.model != 'sale.order':
            return result

        multi_mode = True
        if isinstance(res_ids, int):
            res_ids = [res_ids]
            multi_mode = False
        if self.model == 'sale.order':
            for record in self.env[self.model].browse(res_ids):
                so_print_name = self._render_field('report_name', record.ids, compute_lang=True)[record.id]
                new_attachments = []
                qr_report_name = 'Cover Letter-' + so_print_name + '.pdf'
                qr_pdf = self.env.ref('ia_sale_report.report_sale_cover_letter')._render_qweb_pdf(record.ids)[0]
                qr_pdf = base64.b64encode(qr_pdf)
                new_attachments.append((qr_report_name, qr_pdf))
                record_dict = multi_mode and result[record.id] or result
                attachments_list = record_dict.get('attachments', False)
                if attachments_list:
                    attachments_list.extend(new_attachments)
                else:
                    record_dict['attachments'] = new_attachments

        return result
