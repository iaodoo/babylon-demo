# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class Project(models.Model):
    _inherit = 'project.project'

    @api.model_create_multi
    def create(self, vals_list):
        """ Create an analytic account if project created from sale
        """
        if self.env.context.get('auto_create_analytic_account', False):
            defaults = self.default_get(['analytic_account_id'])
            for values in vals_list:
                analytic_account_id = values.get('analytic_account_id', defaults.get('analytic_account_id'))
                if not analytic_account_id:
                    analytic_account = self._create_analytic_account_from_values(values)
                    values['analytic_account_id'] = analytic_account.id
        return super(Project, self).create(vals_list)

    def write(self, vals):
        if 'active' in vals:
            # archiving/unarchiving a project does it on its analytic account, too
            self.with_context(active_test=False).analytic_account_id.write({'active': vals['active']})
        return super(Project, self).write(vals)
