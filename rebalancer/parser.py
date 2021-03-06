from decimal import Decimal
from csv import DictReader
from collections import namedtuple
from io import TextIOWrapper
from itertools import filterfalse

from .utils import is_sweep

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

def parse_file_object(file):
    AccountEntry = namedtuple('AccountEntry',
                              'account_name symbol share_price current_value is_sweep description shares is_credit')
    ret = []
    account_sweeps = {}
    r = DictReader(file)
    for row in r:
        symbol = row["Symbol"]
        account = row["Account Name/Number"]
        description = row["Description"]
        # If there is no symbol (which happens with some 401(k) funds), try
        # to use the description as the symbol
        if symbol is None or len(symbol) == 0:
            symbol = description

        if symbol is not None and len(symbol) > 0:
            if account not in account_sweeps:
                account_sweeps[account] = False

            sweep = is_sweep(symbol)
            credit = symbol == "Pending Activity"
            symbol = symbol.replace('*', '')

            unity = Decimal(1.0)

            current_value = parse_number_column(row["Current Value"])
            shares = parse_number_column(row["Quantity"], current_value)
            cost_per_share = unity if sweep else parse_number_column(row["Last Price"], unity)

            entry = AccountEntry(account,
                                 symbol,
                                 cost_per_share,
                                 current_value,
                                 sweep,
                                 description,
                                 shares,
                                 credit)

            if sweep:
                account_sweeps[account] = True

            ret.append(entry)

    for (account, has_sweep) in filterfalse(lambda x: x[1], account_sweeps.items()):
        entry = AccountEntry(account,
                             "CORE",
                             Decimal(1.0),
                             Decimal(0.0),
                             True,
                             "Core Account",
                             Decimal(0.0),
                             False)

        ret.append(entry)

    return ret

