from odoo import fields, models, api

class ReportAccountFinancialReport(models.Model):
    _inherit = "account.financial.html.report"

    income = fields.Float(string='Income')

    def _get_table(self, options):
        if self == self.env.ref('account_reports.account_financial_report_balancesheet0'):
            self = self.with_context(exclude_from_date=True)
        headers, lines = super(ReportAccountFinancialReport, self.with_context(print_mode=False))._get_table(options)

        income = {}
        for line in lines:
            if line.get('name') == 'Operating Income' or line.get('id') == 5:
                income = line
                break
        if income:
            t = income['columns'][0].get('no_format')
            for l in lines:
                style_col = False
                for dict in l.get('columns'):
                    if 'percent' in dict.keys():
                        style_col = True
                        break
                if l.get('columns', False) and len(l.get('columns', False)) == 1  or (self.user_has_groups('base.group_no_one') and len(l.get('columns', False))>=2 and not style_col) and (l.get('class') not in ['o_account_reports_totals_below_sections','total'] or l.get('name') in ('Total Gross Profit', 'Cost of Revenue', 'Direct Labor', 'Operating Income', 'Other Income')):
                    if l.get('caret_options') or l.get('id') == 'total_6' or l.get('name') in ('Total Gross Profit', 'Cost of Revenue', 'Direct Labor', 'Operating Income', 'Other Income') or l.get(
                            'id') == 4 and l.get('class') == 'total':
                        s = l['columns'][0].get('no_format')
                        p = t > 0.0 and (s / t) * 100 or 0.0
                        l['columns'].append({
                            'name': '{0:0.2f}%'.format(p),
                            'no_format': p,
                            'class': 'number'
                        })
            headers[0].append({'name': '%', 'class': 'number', 'colspan': 1})
        return headers, lines

    @api.model
    def _build_lines_hierarchy(self, options_list, financial_lines, solver, groupby_keys):
        ''' OVERRIDE
        To implement %
        '''

        lines = []
        income = {}
        for financial_line in financial_lines:

            is_leaf = solver.is_leaf(financial_line)
            has_lines = solver.has_move_lines(financial_line)

            financial_report_line = self._get_financial_line_report_line(
                options_list[0],
                financial_line,
                solver,
                groupby_keys,
            )

            # Manage 'hide_if_zero' field.
            if financial_line.hide_if_zero and all(self.env.company.currency_id.is_zero(column['no_format'])
                                                   for column in financial_report_line['columns'] if 'no_format' in column):
                continue

            # Manage 'hide_if_empty' field.
            if financial_line.hide_if_empty and is_leaf and not has_lines:
                continue

            lines.append(financial_report_line)

            aml_lines = []
            if financial_line.children_ids:
                # Travel children.
                lines += self._build_lines_hierarchy(options_list, financial_line.children_ids, solver, groupby_keys)
            elif is_leaf and financial_report_line['unfolded']:
                # Fetch the account.move.lines.
                solver_results = solver.get_results(financial_line)
                sign = solver_results['amls']['sign']
                for groupby_id, display_name, results in financial_line._compute_amls_results(options_list, self, sign=sign):
                    aml_lines.append(self._get_financial_aml_report_line(
                        options_list[0],
                        financial_report_line['id'],
                        financial_line,
                        groupby_id,
                        display_name,
                        results,
                        groupby_keys,
                    ))
            lines += aml_lines

            if self.env.company.totals_below_sections and (financial_line.children_ids or (is_leaf and financial_report_line['unfolded'] and aml_lines)):
                lines.append(self._get_financial_total_section_report_line(options_list[0], financial_report_line))
                financial_report_line["unfolded"] = True  # enables adding "o_js_account_report_parent_row_unfolded" -> hides total amount in head line as it is displayed later in total line
           # if financial_line.id == 4:
            for line in lines:
                if line.get('name') == 'Operating Income' or line.get('id') == 5:
                    income = line
                    break
            if income or self.income:
                if income:
                    self.income = income['columns'][0].get('no_format')
                t = self.income
                for l in lines:
                    style_col = False
                    for dict in l.get('columns'):
                        if 'percent' in dict.keys():
                            style_col = True
                            break
                    if l.get('columns', False) and len(l.get('columns', False)) == 1 and l.get('class') not in ['o_account_reports_totals_below_sections','total'] or (self.user_has_groups('base.group_no_one') and len(l.get('columns', False))>=2 and not style_col):
                            if l.get('caret_options') or l.get('id') == 'total_6' or l.get('name') in ('Total Gross Profit', 'Cost of Revenue', 'Direct Labor', 'Operating Income', 'Other Income') or l.get(
                                    'id') == 4 and l.get('class') == 'total':
                                s = l['columns'][0].get('no_format')
                                p = t > 0.0 and (s / t) * 100 or 0.0
                                l['columns'].append({
                                    'name': '{0:0.2f}%'.format(p),
                                    'no_format': p,
                                    'class': 'number',
                                    'percent':True
                                })
        return lines



    @api.model
    def _get_options_date_domain(self, options):
        if not options.get('exclude_from_date'):
            return super()._get_options_date_domain(options)
        def create_date_domain(options_date):
            date_field = options_date.get('date_field', 'date')
            domain = [(date_field, '<=', options_date['date_to'])]
            date_tmp = fields.Date.from_string(options_date['date_to'])
            date_tmp = self.env.company.compute_fiscalyear_dates(date_tmp)['date_from']
            date_from = date_tmp.strftime('%Y-%m-%d')
            domain += [(date_field, '>=', date_from)]
            if options_date['mode'] == 'range' and options_date['date_from'] and not options.get('exclude_from_date'):
                strict_range = options_date.get('strict_range')
                if not strict_range:
                    domain += [
                        '|',
                        (date_field, '>=', options_date['date_from']),
                        ('account_id.user_type_id.include_initial_balance', '=', True)
                    ]
                else:
                    domain += [(date_field, '>=', options_date['date_from'])]
            return domain

        if not options.get('date'):
            return []
        return create_date_domain(options['date'])


class AccountFinancialReportLine(models.Model):
    _inherit = "account.financial.html.report.line"

    def _get_options_financial_line(self, options, calling_financial_report, parent_financial_report):
        res = super()._get_options_financial_line(options, calling_financial_report, parent_financial_report)
        # input((self.code, self._context.get('exclude_from_date')))
        if self. code  in ('PREV_YEAR_EARNINGS', 'NEP', 'CURR_YEAR_EARNINGS', 'OPINC', 'OIN', 'COS', 'EXP', 'DEP') and self._context.get('exclude_from_date'):
            res.update({'exclude_from_date': True})
        return res
