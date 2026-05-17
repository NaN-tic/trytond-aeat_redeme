# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    aeat_redeme_account = fields.MultiValue(fields.Many2One(
            'account.account', 'REDEME Account',
            domain=[
                ('closed', '=', False),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ('type.payable', '=', True),
                ],
            help='Account used as invoice counterpart for supplier invoices '
            'with REDEME taxes mapped to box 77.'))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'aeat_redeme_account':
            return pool.get('account.configuration.aeat303')
        return super().multivalue_model(field)


class ConfigurationAEAT303(metaclass=PoolMeta):
    __name__ = 'account.configuration.aeat303'

    aeat_redeme_account = fields.Many2One(
        'account.account', 'REDEME Account',
        domain=[
            ('closed', '=', False),
            ('company', '=', Eval('company', -1)),
            ('type.payable', '=', True),
            ],
        help='Account used as invoice counterpart for supplier invoices with '
        'REDEME taxes mapped to box 77.')
