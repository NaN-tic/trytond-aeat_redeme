import datetime
import unittest
from decimal import Decimal

from proteus import Model, Wizard
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

        activate_modules(['aeat_redeme', 'account_es', 'account_invoice'])

        eur = get_currency('EUR')
        _ = create_company(currency=eur)
        company = get_company()

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
        revenue, = Account.find([
            ('type.revenue', '=', True),
            ('code', '=', '7000'),
            ('company', '=', company.id),
        ], limit=1)
        expense, = Account.find([
            ('type.expense', '=', True),
            ('code', '=', '600'),
            ('company', '=', company.id),
        ], limit=1)
        create_chart.form.account_receivable = receivable
        create_chart.form.account_payable = payable
        create_chart.execute('create_properties')

        Party = Model.get('party.party')
        party = Party(name='Party')
        identifier = party.identifiers.new()
        identifier.type = 'eu_vat'
        identifier.code = 'ES00000000T'
        party.save()

        Tax = Model.get('account.tax')
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        tax, = Tax.find([
            ('group.kind', '=', 'sale'),
            ('name', '=', 'IVA 21%'),
            ('parent', '=', None),
        ], limit=1)
        account_category.customer_taxes.append(tax)
        tax, = Tax.find([
            ('group.kind', '=', 'purchase'),
            ('name', '=', 'IVA Deducible 21% (operaciones corrientes)'),
            ('parent', '=', None),
        ], limit=1)
        account_category.supplier_taxes.append(tax)
        account_category.save()

        import_category = ProductCategory(name="Import Category")
        import_category.accounting = True
        import_category.account_expense = expense
        import_category.account_revenue = revenue
        tax, = Tax.find([
            ('group.kind', '=', 'purchase'),
            ('name', '=', 'IVA 21% Importaciones (Bienes corrientes)'),
            ('parent', '=', None),
        ], limit=1)
        import_category.supplier_taxes.append(tax)
        import_category.save()

        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'service'
        template.list_price = Decimal('40')
        template.account_category = account_category
        product, = template.products
        product.cost_price = Decimal('25')
        template.save()
        product, = template.products

        import_template = ProductTemplate()
        import_template.name = 'import_product'
        import_template.default_uom = unit
        import_template.type = 'goods'
        import_template.list_price = Decimal('100')
        import_template.account_category = import_category
        import_product, = import_template.products
        import_product.cost_price = Decimal('100')
        import_template.save()
        import_product, = import_template.products

        payment_term = create_payment_term()
        payment_term.save()

        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.party = party
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = product
        line.unit_price = Decimal('40.0')
        line.quantity = 5
        line = invoice.lines.new()
        line.account = revenue
        line.description = 'Test'
        line.quantity = 1
        line.unit_price = Decimal(20)
        line = invoice.lines.new()
        line.account = revenue
        line.description = 'Test 2'
        line.quantity = 1
        line.unit_price = Decimal(40)
        tax, = Tax.find([
            ('group.kind', '=', 'sale'),
            ('name', '=', 'IVA 21%'),
            ('parent', '=', None),
        ], limit=1)
        line.taxes.append(tax)
        invoice.click('post')

        invoice = Invoice()
        invoice.type = 'in'
        invoice.invoice_date = today
        invoice.party = party
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = import_product
        line.unit_price = Decimal('100.0')
        line.quantity = 1
        line.account = expense
        invoice.click('post')

        Report = Model.get('aeat.303.report')
        report = Report()
        report.year = today.year
        report.type = 'I'
        report.regime_type = '3'
        report.period = "%02d" % (today.month)
        report.return_sepa_check = '0'
        report.exonerated_mod390 = '0' if report.period != '12' else '2'
        report.company_vat = '123456789'
        report.click('calculate')
        self.assertEqual(report.aduana_tax_pending, Decimal('0.00'))

        company.redeme = True
        company.save()

        report = Report()
        report.year = today.year
        report.type = 'I'
        report.regime_type = '3'
        report.period = "%02d" % (today.month)
        report.return_sepa_check = '0'
        report.exonerated_mod390 = '0' if report.period != '12' else '2'
        report.company_vat = '123456789'
        report.click('calculate')
        self.assertEqual(report.aduana_tax_pending, Decimal('21.00'))
