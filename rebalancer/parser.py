from decimal import Decimal
from csv import DictReader
from collections import namedtuple
from io import TextIOWrapper
from itertools import filterfalse

from .utils import CORE

class CaseInsensitiveDictReader(DictReader):
    @property
    def fieldnames(self):
        names = super().fieldnames
        return [name.casefold() for name in names] if names is not None else names

    @fieldnames.setter
    def fieldnames(self, value):
        DictReader.fieldnames.fset(self, value)

def parse_number_column(val, default=None):
    if default is None:
        return Decimal(val.replace(',', '').replace('$', ''))
    else:
        return default if val is None or len(val) == 0 else parse_number_column(val)

def parse_file(file):
    if hasattr(file, 'read'):
        with TextIOWrapper(file, encoding='utf-8-sig') as f:
            return parse_file_object(f)
    else:
        with open(file, "r", encoding='utf-8-sig') as f:
            return parse_file_object(f)

def get_account_number(row):
    try:
        return row["account number"]
    except KeyError:
        return row["account name/number"]

def parse_file_object(file):
    AccountEntry = namedtuple('AccountEntry',
                              'account_name symbol share_price current_value description shares')
    ret = []
    r = CaseInsensitiveDictReader(file)
    for row in r:
        symbol = row["symbol"]
        account = get_account_number(row)
        description = row["description"]
        # If there is no symbol (which happens with some 401(k) funds), try
        # to use the description as the symbol
        if symbol is None or len(symbol) == 0:
            symbol = description

        if symbol is not None and len(symbol) > 0:
            credit = symbol.casefold() == "Pending Activity".casefold()
            symbol = CORE if credit else symbol.replace('*', '')

            unity = Decimal(1.0)

            current_value = parse_number_column(row["current value"])
            shares = parse_number_column(row["quantity"], current_value)
            cost_per_share = parse_number_column(row["last price"], unity)

            entry = AccountEntry(account,
                                 symbol,
                                 cost_per_share,
                                 current_value,
                                 description,
                                 shares)

            ret.append(entry)

    return ret

