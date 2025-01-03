# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
from dateutil.relativedelta import relativedelta
import calendar
import csv
from odoo.tools import float_round
import base64
import math


class GenerateCommission(models.TransientModel):
    _name = 'generate.sales.commission'
    _description = 'Generate Sales commission'

    @api.model
    def _get_months(self):
        res = []
        startdate = datetime.now()
        for i in range(0,12):
            date = startdate - relativedelta(months=i)
            key = format(date, '%m-%Y')
            value = format(date, '%B %Y')
            res.append((key, value))
        return res

    month = fields.Selection(string="Month", selection=_get_months, required=True)
    csv_file_diff = fields.Binary()


    def generate_commission(self):
        return self.env.ref('sales_commission.commission_audit_report').report_action(self)

    def get_commission_vals(self):

        commission_vals = {}
        month = self.month.split('-')[0]
        year = self.month.split('-')[1]

        month_last_date = calendar.monthrange(int(year), int(month))[1]
        from_date = "%s%s01" % (year, month)
        from_date = datetime.strptime(from_date, "%Y%m%d").date()
        to_date = "%s%s%s" % (year, month, month_last_date)
        to_date = datetime.strptime(to_date, "%Y%m%d").date()


        fiscal_date_from = to_date - relativedelta(years=1)

        invoices = self.env['account.move'].search([('payment_state', 'in', ('in_payment', 'paid')),
                                                    ('move_type', 'in', ('out_invoice', 'out_refund')),
                                                    ('check_bounce_invoice', '=', False), ('invoice_date_due', '>=', fiscal_date_from)])

        for invoice in invoices:
            if invoice.paid_date and from_date <= invoice.paid_date <= to_date:
                for rec in invoice.commission_rule_ids:
                    commission = 0
                    profit = invoice.gross_profit
                    if rec.based_on in ['profit', 'profit_delivery']:
                        if profit <= 0:
                            continue
                        commission = profit * (rec.percentage / 100)
                    elif rec.based_on == 'invoice':
                        amount = invoice.amount_total
                        commission = amount * (rec.percentage / 100)
                    if commission == 0:
                        continue
                    invoice_type = 'Invoice'
                    if invoice.move_type == 'out_refund':
                        commission = -commission
                        invoice_type = 'Refund'

                    sale = invoice.invoice_line_ids.mapped('sale_line_ids').mapped('order_id')
                    vals = {
                        'sale_person_id': rec.sales_person_id,
                        'sale_id': sale and sale,
                        'commission': commission,
                        'invoice_id': invoice,
                        'invoice_type': invoice_type,
                        'is_paid': True,
                        'invoice_amount': invoice.amount_total,
                        'commission_date': invoice.invoice_date and invoice.paid_date
                    }

                    if commission_vals.get(rec.sales_person_id):
                        if commission_vals.get(rec.sales_person_id).get(invoice.partner_id):
                            if commission_vals.get(rec.sales_person_id).get(invoice.partner_id).get(invoice):
                                commission_vals[rec.sales_person_id][invoice.partner_id][invoice].append(vals)
                            else:
                                commission_vals[rec.sales_person_id][invoice.partner_id][invoice] = [vals]
                        else:
                            commission_vals[rec.sales_person_id][invoice.partner_id] = {invoice: [vals]}
                    else:
                        commission_vals[rec.sales_person_id] = {invoice.partner_id: {invoice: [vals]}}

                    if invoice.move_type != 'out_refund' and invoice.paid_date > invoice.invoice_date_due:

                        extra_days = invoice.paid_date - invoice.invoice_date_due
                        if self.env.user.company_id.commission_ageing_ids:
                            commission_ageing = self.env.user.company_id.commission_ageing_ids.filtered(
                                lambda r: r.delay_days <= extra_days.days)
                            commission_ageing = commission_ageing.sorted(key=lambda r: r.delay_days, reverse=True)
                            if commission_ageing and commission_ageing[0].reduce_percentage:
                                commission = commission_ageing[0].reduce_percentage * commission / 100
                                vals = {
                                    'sale_person_id': rec.sales_person_id,
                                    'sale_id': sale,
                                    'commission': -commission,
                                    'invoice_id': invoice,
                                    'invoice_type': 'Commission Aging',
                                    'is_paid': True,
                                    'invoice_amount': invoice.amount_total,
                                    'commission_date': invoice.paid_date
                                }
                                if commission_vals.get(rec.sales_person_id):
                                    if commission_vals.get(rec.sales_person_id).get(invoice.partner_id):
                                        if commission_vals.get(rec.sales_person_id).get(invoice.partner_id).get(invoice):
                                            commission_vals[rec.sales_person_id][invoice.partner_id][invoice].append(vals)
                                        else:
                                            commission_vals[rec.sales_person_id][invoice.partner_id][invoice] = [vals]
                                    else:
                                        commission_vals[rec.sales_person_id][invoice.partner_id] = {invoice: [vals]}
                                else:
                                    commission_vals[rec.sales_person_id] = {invoice.partner_id: {invoice: [vals]}}
        return commission_vals

    def generate_diff_csv(self):

        commission_vals = self.get_commission_vals()
        commission_diff = {}
        for rep, partners in commission_vals.items():
            for partner, invoices in partners.items():
                for invoice, vals_list in invoices.items():
                    commission = 0
                    for vals in vals_list:
                        commission += vals.get('commission')

                    non_setteled = invoice.mapped('sale_commission_ids').filtered(lambda r: r.sale_person_id == rep and r.is_paid and not r.is_settled)
                    if not non_setteled:
                        continue
                    old_commission_lines = invoice.mapped('sale_commission_ids').filtered(lambda r: r.sale_person_id == rep and r.is_paid)
                    old_commission = old_commission_lines and sum(old_commission_lines.mapped('commission')) or 0
                    diffrence = float_round(commission, precision_digits=2) - float_round(old_commission, precision_digits=2)
                    if float_round(commission, precision_digits=2) != float_round(old_commission, precision_digits=2):
                        if math.isclose(commission, old_commission, abs_tol=0.1):
                            diffrence = 0
                    vals1 = {'old_commission': float_round(old_commission, precision_digits=2),
                             'commission_audit': float_round(commission, precision_digits=2),
                             'diffrence': float_round(diffrence, precision_digits=2)}
                    if commission_diff.get(rep):
                        if commission_diff.get(rep).get(partner):
                            if commission_diff.get(rep).get(partner).get(invoice):
                                commission_diff[rep][partner][invoice].append(vals1)
                            else:
                                commission_diff[rep][partner][invoice] = [vals1]
                        else:
                            commission_diff[rep][partner] = {invoice: [vals1]}
                    else:
                        commission_diff[rep] = {partner: {invoice: [vals1]}}


        with open('commission.csv', mode='w') as file:
            writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(['Invoice', 'Partner', 'SaleRep', 'Commission', 'Real Commission', 'Diff'])
            for salerep, partners in commission_diff.items():
                for partner, moves in partners.items():
                    for move, vals in moves.items():

                        inv = move.name
                        part = partner.name
                        rep = salerep.name
                        commission = vals[0].get('old_commission')
                        realcommission = vals[0].get('commission_audit')
                        diff = vals[0].get('diffrence')
                        writer.writerow([inv, part, rep, commission, realcommission, diff])
        with open('commission.csv', 'r', encoding="utf-8") as f2:
            data = str.encode(f2.read(), 'utf-8')
        self.csv_file_diff = base64.encodebytes(data)

        return {
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=generate.sales.commission&id=" + str(self.id) +
            "&filename=commission.csv&field=csv_file_diff&download=true&name_file=commission",
            'target': 'self',
            }







# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
