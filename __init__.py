# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import aeat
from . import company


def register():
    Pool.register(
        company.Company,
        aeat.Report,
        module='aeat_redeme', type_='model')
