from decimal import Decimal
from csv import DictReader
from collections import namedtuple
from io import TextIOWrapper

from .utils import is_sweep

def parse_dollar_column(val):
    if val[0] == '$':
        return Decimal(val[1:])
    else:
        return Decimal(val)

def parse_file(file):
    if hasattr(file, 'read'):
        with TextIOWrapper(file, encoding='utf-8') as f:
            return parse_file_object(f)
    else:
        with open(file, "r") as f:
            return parse_file_object(f)

def parse_file_object(file):
    AccountEntry = namedtuple('AccountEntry',
                              'account_name symbol share_price current_value is_sweep description')
    ret = []
    r = DictReader(file)
    for row in r:
        symbol = row["Symbol"]
        account = row["Account Name/Number"]
        description = row["Description"]
        if len(symbol) > 0:
            sweep = is_sweep(symbol)
            symbol = symbol.replace('*', '')

            cost_per_share = Decimal(1.0) if sweep else parse_dollar_column(row["Last Price"])
            current_value = None
            current_value = parse_dollar_column(row["Current Value"])

            entry = AccountEntry(account,
                                 symbol,
                                 cost_per_share,
                                 current_value,
                                 sweep,
                                 description)

            ret.append(entry)

    return ret

