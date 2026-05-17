# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import Workflow, ModelView, fields
from trytond.modules.aeat_303.aeat import _Z
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Report(metaclass=PoolMeta):
    __name__ = 'aeat.303.report'

    company_redeme = fields.Function(fields.Boolean('REDEME'),
        'on_change_with_company_redeme')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        if 'readonly' in cls.aduana_tax_pending.states:
            cls.aduana_tax_pending.states['readonly'] |= ~Eval(
                'company_redeme', False)
        else:
            cls.aduana_tax_pending.states['readonly'] = ~Eval(
                'company_redeme', False)
        cls.aduana_tax_pending.depends.add('company_redeme')

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

    def get_move_counterpart_amount(self):
        amount = super().get_move_counterpart_amount()
        if self.company and self.company.redeme:
            amount -= self.aduana_tax_pending or _Z
        return amount
