# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.exceptions import UserWarning
from trytond.i18n import gettext
from trytond.pool import Pool, PoolMeta


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def _get_redeme_code_tax_ids(cls, company):
        pool = Pool()
        Mapping = pool.get('aeat.303.mapping')

        code_ids = set()
        for mapping in Mapping.search([
                    ('type_', '=', 'code'),
                    ('company', '=', company.id),
                    ('aeat303_field.name', '=', 'aduana_tax_pending'),
                    ]):
            code_ids.update(code.id for code in mapping.code_by_companies)
        return code_ids

    def _is_redeme_tax(self, invoice_tax, code_ids):
        if not invoice_tax.tax:
            return False
        type_ = 'invoice' if (invoice_tax.base or 0) >= 0 else 'credit'
        for code_line in invoice_tax.tax.code_lines:
            if code_line.amount != 'tax' or code_line.type != type_:
                continue
            if code_line.code.id in code_ids:
                return True
        return False

    @classmethod
    def _post(cls, invoices):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        Warning = pool.get('res.user.warning')

        code_ids_by_company = {}
        to_save = []
        for invoice in invoices:
            if invoice.type != 'in' or not invoice.company.redeme:
                continue
            if invoice.lines or len(invoice.taxes) != 1:
                continue
            invoice_tax, = invoice.taxes
            code_ids = code_ids_by_company.setdefault(
                invoice.company.id,
                cls._get_redeme_code_tax_ids(invoice.company))
            if not code_ids or not invoice._is_redeme_tax(
                    invoice_tax, code_ids):
                continue
            config = Configuration(1)
            account = config.get_multivalue(
                'aeat_redeme_account', company=invoice.company.id)
            if account and invoice.account != account:
                key = 'aeat_redeme_account_change_%s' % invoice.id
                if Warning.check(key):
                    raise UserWarning(key, gettext(
                            'aeat_redeme.msg_redeme_account_change',
                            invoice=invoice.rec_name,
                            account=account.rec_name))
                invoice.account = account
                to_save.append(invoice)
        if to_save:
            cls.save(to_save)
        super()._post(invoices)
