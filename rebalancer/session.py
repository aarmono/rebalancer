from types import SimpleNamespace
from collections import defaultdict, namedtuple
from decimal import Decimal
from functools import partial

from .db import Database
from .utils import to_enum_name, is_mutual_fund
from .crypto import hash_user_token, hash_account_name, decrypt_account_description
from .parser import parse_file, parse_file_object
from .securities import SecurityDatabase
from .portfolio import Portfolio
from .target import AccountTarget
from .rebalance import Rebalancer

def create_tax_status(database):
    tax_status = {}
    for (name, _) in database.get_tax_groups():
        tax_status[to_enum_name(name)] = name

    TaxStatusClass = namedtuple('TaxStatusClass', ' '.join(tax_status.keys()))
    return TaxStatusClass(*tax_status.values())

def get_account_info(database, user_token, account, account_name):
    return database.get_account_info(user_token, account_hash, account_name)

class Session:
    def __init__(self,
                 user_token,
                 db,
                 filename = None,
                 taxable_credit = None,
                 tax_deferred_credit = None,
                 quote_key = None,
                 fractional_shares = False):
        self.__user_token = user_token
        self.__account_info = {}

        self.__account_entries = None if filename is None else parse_file(filename)
        self.__securities_db = SecurityDatabase(self.__account_entries, db, quote_key, fractional_shares)
        self.__account_target = AccountTarget(user_token, self.__securities_db, db)
        self.__rebalancer = Rebalancer(self.__securities_db, self.__account_target)

        self.__portfolio = None
        if self.__account_entries is not None:
            account_names = set(map(lambda x: x.account_name,
                                    self.__account_entries))

            account_info_iter = db.get_account_infos(user_token, account_names)
            self.__account_info = dict(zip(account_names, account_info_iter))

            TaxStatus = create_tax_status(db)
            self.__portfolio = Portfolio(self.__securities_db, TaxStatus)

            #credits = self.__get_credit_dict(TaxStatus, db, taxable_credit, tax_deferred_credit)

            for account_entry in self.__account_entries:
                if self.__securities_db.contains_symbol(account_entry.symbol):
                    info = self.__get_account_info(db, account_entry.account_name)
                    if info is not None:
                        current_value = account_entry.current_value
                        description = info.description if info.description is not None else account_entry.account_name

                        self.__portfolio.add_position(description,
                                                      info.tax_status,
                                                      account_entry.symbol,
                                                      current_value)

            for (account_name, account_info) in self.__account_info.items():
                if account_info is not None and account_info.is_default != 0:
                    if taxable_credit is not None and account_info.tax_status == TaxStatus.TAXABLE:
                        description = account_info.description if account_info.description is not None else account_entry.account_name

                        self.__portfolio.add_position(description,
                                                      account_info.tax_status,
                                                      'CORE',
                                                      taxable_credit)

                    if tax_deferred_credit is not None and account_info.tax_status == TaxStatus.TAX_DEFERRED:
                        description = account_info.description if account_info.description is not None else account_entry.account_name

                        self.__portfolio.add_position(description,
                                                      account_info.tax_status,
                                                      'CORE',
                                                      tax_deferred_credit)

    def get_portfolio(self):
        return self.__portfolio

    def get_securities_db(self):
        return self.__securities_db

    def get_rebalancer(self):
        return self.__rebalancer

    def get_account_target(self):
        return self.__account_target

    def get_account_entries(self):
        return self.__account_entries.copy()

    def __get_account_info(self, database, account_name):
        if account_name not in self.__account_info:
            info = database.get_account_info(self.__user_token, account_name)
            self.__account_info[account_name] = info

        return self.__account_info[account_name]
