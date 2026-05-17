# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import aeat
from . import company
from . import configuration
from . import invoice


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationAEAT303,
        company.Company,
        aeat.Report,
        invoice.Invoice,
        module='aeat_redeme', type_='model')
