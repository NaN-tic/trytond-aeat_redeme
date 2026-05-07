# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import Workflow, ModelView, fields
from trytond.modules.aeat_303.aeat import _Z
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Report(metaclass=PoolMeta):
    __name__ = 'aeat.303.report'

    company_redeme = fields.Function(fields.Boolean('REDEME'),
        'on_change_with_company_redeme')
    aduana_tax_pending = fields.Numeric(
        'Aduana Tax Pending', digits=(15, 2),
        help="Import VAT paid by Aduana pending entry",
        states={
            'readonly': ~Eval('company_redeme', False),
            },
        depends=['company_redeme'])

    @fields.depends('company')
    def on_change_with_company_redeme(self, name=None):
        return bool(self.company and self.company.redeme)

    @classmethod
    @ModelView.button
    @Workflow.transition('calculated')
    def calculate(cls, reports):
        super().calculate(reports)
        to_save = []
        for report in reports:
            if not report.company.redeme and report.aduana_tax_pending:
                report.aduana_tax_pending = _Z
                to_save.append(report)
        if to_save:
            cls.save(to_save)

    def create_move(self):
        pool = Pool()
        Company = pool.get('company.company')
        Mapping = pool.get('aeat.303.mapping')
        TaxCode = pool.get('account.tax.code')
        Tax = pool.get('account.tax')
        TaxLine = pool.get('account.tax.line')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Config = pool.get('account.configuration')

        if not self.move_account or not self.move_journal:
            return

        prorrata_account = Config(1).aeat303_prorrata_account

        codes = []
        aduana_codes = set()
        for mapp in Mapping.search([
                ('type_', '=', 'code'),
                ('company', '=', self.company),
                ]):
            if (not self.company.redeme
                    and mapp.aeat303_field.name == 'aduana_tax_pending'):
                continue
            code_ids = [x.id for x in mapp.code_by_companies]
            codes.extend(code_ids)
            if mapp.aeat303_field.name == 'aduana_tax_pending':
                aduana_codes.update(code_ids)
        if not codes:
            return

        periods = self.get_periods()
        description = self.move_description or 'AEAT 303'
        with Transaction().set_context(periods=periods):
            mapp_code_lines = {}
            aduana_amount = _Z
            for code in TaxCode.browse(codes):
                if not code.amount:
                    continue

                children = []
                childs = TaxCode.search([
                        ('parent', 'child_of', [code]),
                        ])
                if len(childs) == 1:
                    children = childs
                else:
                    for child in childs:
                        if not child.childs and child.amount:
                            children.append(child)
                for child in children:
                    if not child.lines:
                        continue
                    domain = [['OR'] + [x._line_domain for x in child.lines
                        if x.amount == 'tax']]
                    if domain == [['OR']]:
                        continue
                    domain.extend(Tax._amount_domain())
                    tax_lines = TaxLine.search(domain)
                    mapp_code_lines[child] = [x.move_line for x in tax_lines]
                    if child.id in aduana_codes:
                        aduana_amount += sum(
                            ((x.move_line.debit or _Z)
                                - (x.move_line.credit or _Z))
                            for x in tax_lines)
            if not mapp_code_lines:
                return

            move = Move()
            move.journal = self.move_journal
            move.period = periods[-1]
            move.date = move.period.end_date
            move.origin = self
            move.state = 'draft'
            move.description = description
            move.save()

            move_lines = {}
            for code, lines in mapp_code_lines.items():
                for line in lines:
                    key = (code, line.account)
                    if key in move_lines:
                        move_lines[key].credit += line.debit
                        move_lines[key].debit += line.credit
                    else:
                        move_line = MoveLine()
                        move_line.move = move
                        move_line.account = line.account
                        move_line.credit = line.debit
                        move_line.debit = line.credit
                        move_line.description = code.name
                        move_lines[key] = move_line

        counterpart_line = MoveLine()
        counterpart_line.move = move
        counterpart_line.account = self.move_account
        company = Company(self.company.id)
        amount = self.liquidation_result
        if self.post_and_close and company.redeme:
            amount -= aduana_amount
        if amount >= 0:
            counterpart_line.credit = amount
            counterpart_line.debit = _Z
        else:
            counterpart_line.debit = -amount
            counterpart_line.credit = _Z
        counterpart_line.description = description

        lines = []
        for _, line in move_lines.items():
            if line.debit and line.credit:
                balance = line.debit - line.credit
                if balance == _Z:
                    continue
                elif balance >= _Z:
                    line.debit = balance
                    line.credit = _Z
                else:
                    line.credit = -balance
                    line.debit = _Z
            lines.append(line)
        lines_to_save = lines + [counterpart_line]
        debit = self.calculate_prorrata_debit()
        if debit and prorrata_account:
            prorrata_line = MoveLine()
            prorrata_line.move = move
            prorrata_line.account = prorrata_account
            prorrata_line.debit = debit
            prorrata_line.credit = _Z
            prorrata_line.description = (
                'Prorrata regularization')
            lines_to_save.append(prorrata_line)

        MoveLine.save(lines_to_save)
        self.move = move
        self.save()
