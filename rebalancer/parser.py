from decimal import Decimal
from csv import DictReader
from collections import namedtuple
from io import TextIOWrapper

from .utils import is_sweep

def parse_dollar_column(val, default=None):
    if default is None:
        return Decimal(val.replace(',', '').replace('$', ''))
    else:
        return default if val is None or len(val) == 0 else parse_dollar_column(val)

def parse_number_column(val, default):
    return default if val is None or len(val) == 0 else Decimal(val.replace(',', ''))

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
            sweep = is_sweep(symbol)
            credit = symbol == "Pending Activity"
            symbol = symbol.replace('*', '')

            unity = Decimal(1.0)

            current_value = parse_dollar_column(row["Current Value"])
            shares = parse_number_column(row["Quantity"], current_value)
            cost_per_share = unity if sweep else parse_dollar_column(row["Last Price"], unity)

            entry = AccountEntry(account,
                                 symbol,
                                 cost_per_share,
                                 current_value,
                                 sweep,
                                 description,
                                 shares,
                                 credit)

            ret.append(entry)

    return ret

