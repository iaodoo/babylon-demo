# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class RentalSchedule(models.Model):
    _inherit = "sale.rental.schedule"

    home_depot_id = fields.Many2one('stock.location', 'Home Depot', readonly=True)  

    def _select(self):
        """ OVER RIDE TO REPLACE car_name"""
        super(RentalSchedule, self)._select()
        return """%s,
            %s,
            sol.product_id as product_id,
            t.uom_id as product_uom,
            sol.name as description,
            s.name as name,
            %s,
            s.date_order as order_date,
            sol.pickup_date as pickup_date,
            sol.return_date as return_date,
            s.state as state,
            s.rental_status as rental_status,
            s.partner_id as partner_id,
            s.user_id as user_id,
            s.company_id as company_id,
            extract(epoch from avg(date_trunc('day',sol.return_date)-date_trunc('day',sol.pickup_date)))/(24*60*60)::decimal(16,2) as delay,
            t.categ_id as categ_id,
            s.pricelist_id as pricelist_id,
            s.analytic_account_id as analytic_account_id,
            s.team_id as team_id,
            p.product_tmpl_id,
            partner.country_id as country_id,
            partner.commercial_partner_id as commercial_partner_id,
            case when s.partner_id != partner.commercial_partner_id then CONCAT(commercial_partner.name, ', ', s.name)
            else CONCAT(partner.name, ', ', s.name) 
            end as card_name,
            s.id as order_id,
            sol.id as order_line_id,
            %s,
            %s,
            %s,
            lot_info.lot_id as lot_id,
            s.warehouse_id as warehouse_id,
            (select home_depot_id from stock_production_lot where id = lot_info.lot_id) as home_depot_id
        """ % (
            self._id(), self._get_product_name(), self._quantity(), self._report_line_status(), self._late(),
            self._color())

    def _from(self):
        super(RentalSchedule, self)._from()
        return """
            sale_order_line sol
                join sale_order s on (sol.order_id=s.id)
                join res_partner partner on s.partner_id = partner.id
                left join product_product p on (sol.product_id=p.id)
                left join product_template t on (p.product_tmpl_id=t.id)
                left join uom_uom u on (u.id=sol.product_uom)
                left join uom_uom u2 on (u2.id=t.uom_id)
                LEFT JOIN res_partner commercial_partner ON partner.parent_id = commercial_partner.id
                LEFT OUTER JOIN ordered_lots lot_info ON sol.id=lot_info.sol_id,
                padding pdg
        """

    def _groupby(self):
        return super(RentalSchedule, self)._groupby() + """,
            commercial_partner.name
        """

    # def _from(self):
    #     return """
    #         product_product p              
               
    #             left join sale_order_line sol on (sol.product_id=p.id)
    #             left join sale_order s on (sol.order_id=s.id)
    #             left join res_partner partner on s.partner_id = partner.id
    #             left join product_template t on (p.product_tmpl_id=t.id)
    #             left join uom_uom u on (u.id=sol.product_uom)
    #             left join uom_uom u2 on (u2.id=t.uom_id)
    #             LEFT OUTER JOIN ordered_lots lot_info ON p.id = lot_info.product_id,
    #         padding pdg
    #     """
    
    # def _with(self):
    #     return """
    #         WITH ordered_lots (lot_id, name, sol_id, report_line_status) AS
    #             (SELECT
    #                 lot.id as lot_id,
    #                 lot.name,                    
    #                 COALESCE(res.sale_order_line_id, pickedup.sale_order_line_id) as sol_id,
    #                 CASE
    #                     WHEN returned.stock_production_lot_id IS NOT NULL THEN 'returned'
    #                     WHEN pickedup.stock_production_lot_id IS NOT NULL THEN 'pickedup'
    #                     ELSE 'reserved1'
    #                 END AS report_line_status,
    #                 lot.product_id
    #                 FROM
	# 		stock_production_lot lot		   
    #                 LEFT JOIN rental_reserved_lot_rel res
    #                  ON res.stock_production_lot_id=lot.id
                       
    #                 FULL OUTER JOIN rental_pickedup_lot_rel pickedup
    #                     ON res.sale_order_line_id=pickedup.sale_order_line_id
    #                     AND res.stock_production_lot_id=pickedup.stock_production_lot_id
    #                 LEFT OUTER JOIN rental_returned_lot_rel returned
    #                     ON returned.sale_order_line_id=pickedup.sale_order_line_id
    #                     AND returned.stock_production_lot_id=pickedup.stock_production_lot_id
    #             ),
    #             sol_id_max (id) AS
    #                 (SELECT MAX(id) FROM sale_order_line),
    #             lot_id_max (id) AS
    #                 (SELECT MAX(id) FROM stock_production_lot),
    #             padding (max_id) AS
    #                 (SELECT CASE when lot_id_max > sol_id_max then lot_id_max ELSE sol_id_max END as max_id from lot_id_max, sol_id_max)
    #     """


    # def _query(self):
    #     s = super(RentalSchedule, self)._query() 
    #     p = s.split('\n')
    #     sp = ''
    #     for item in range(0, len(p)):
    #         if item not in (129,130):
    #             sp += p[item] + "\n"
    #     s = sp
    #     return s
    #     # return """
    #     #     %s (SELECT %s
    #     #         FROM %s              
    #     #         GROUP BY %s)
    #     # """ % (
    #     #     self._with(),
    #     #     self._select(),
    #     #     self._from(),
    #     #     self._groupby()
    #     # )

