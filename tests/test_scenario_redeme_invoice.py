import datetime
import unittest
from decimal import Decimal

from proteus import Model, Wizard
from trytond.exceptions import UserWarning
from trytond.modules.account.tests.tools import create_fiscalyear
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.currency.tests.tools import get_currency
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        today = datetime.date.today()

        test_config = activate_modules(
            ['aeat_redeme', 'account_es', 'account_invoice'])
        Module = Model.get('ir.module')
        aeat_redeme_module, = Module.find([('name', '=', 'aeat_redeme')])
        Module.click([aeat_redeme_module], 'upgrade')
        Wizard('ir.module.activate_upgrade').execute('upgrade')

        eur = get_currency('EUR')
        _ = create_company(currency=eur)
        company = get_company()
        company.redeme = True
        company.save()

        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        AccountTemplate = Model.get('account.account.template')
        Account = Model.get('account.account')
        account_template, = AccountTemplate.find([('parent', '=', None),
                                                  ('name', 'ilike',
                                                   'Plan General Contable%')])
        create_chart = Wizard('account.create_chart')
        create_chart.execute('account')
        create_chart.form.account_template = account_template
        create_chart.form.company = company
        create_chart.execute('create_account')
        receivable, = Account.find([
            ('type.receivable', '=', True),
            ('code', '=', '4300'),
            ('company', '=', company.id),
        ], limit=1)
        payable, = Account.find([
            ('type.payable', '=', True),
            ('code', '=', '4100'),
            ('company', '=', company.id),
        ], limit=1)
        alt_payable, = Account.find([
            ('type.payable', '=', True),
            ('code', '=', '4000'),
            ('company', '=', company.id),
        ], limit=1)
        create_chart.form.account_receivable = receivable
        create_chart.form.account_payable = payable
        create_chart.execute('create_properties')

        Config = Model.get('account.configuration')
        config = Config(1)
        config.aeat_redeme_account = payable
        config.save()

        Party = Model.get('party.party')
        party = Party(name='Supplier')
        identifier = party.identifiers.new()
        identifier.type = 'eu_vat'
        identifier.code = 'ES00000000T'
        party.account_payable = alt_payable
        party.save()

        payment_term = create_payment_term()
        payment_term.save()

        Tax = Model.get('account.tax')
        tax, = Tax.find([
            ('group.kind', '=', 'purchase'),
            ('name', '=', 'IVA 21% Importaciones (Bienes corrientes)'),
            ('parent', '=', None),
        ], limit=1)

        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.type = 'in'
        invoice.invoice_date = today
        invoice.party = party
        invoice.payment_term = payment_term
        self.assertFalse(invoice.lines)
        self.assertEqual(invoice.account.id, alt_payable.id)

        invoice_tax = invoice.taxes.new()
        invoice_tax.manual = True
        invoice_tax.tax = tax
        invoice_tax.base = Decimal('100.00')
        self.assertEqual(len(invoice.taxes), 1)
        self.assertEqual(invoice_tax.amount, Decimal('21.00'))

        with self.assertRaises(UserWarning):
            invoice.click('post')

        Warning = Model.get('res.user.warning')
        Warning(user=test_config.user,
            name='aeat_redeme_account_change_%s' % invoice.id,
            always=True).save()
        invoice.click('post')

        self.assertEqual(invoice.account.id, payable.id)
        counterpart_credit = sum(
            l.credit for l in invoice.move.lines if l.account.id == payable.id)
        self.assertEqual(counterpart_credit, Decimal('21.00'))
