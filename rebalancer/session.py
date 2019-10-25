from types import SimpleNamespace
from collections import defaultdict, namedtuple
from decimal import Decimal
from functools import partial

from .db import create_db_conn
from .utils import to_enum_name, is_mutual_fund
from .crypto import hash_user_token, hash_account_name, decrypt_account_description, get_user_salt
from .parser import parse_file, parse_file_object
from .securities import SecurityDatabase
from .portfolio import Portfolio
from .target import AccountTarget
from .rebalance import Rebalancer

def create_tax_status(conn):
    tax_status = {}
    for (name,) in conn.execute('SELECT Name FROM TaxGroups'):
        tax_status[to_enum_name(name)] = name

    TaxStatusClass = namedtuple('TaxStatusClass', ' '.join(tax_status.keys()))
    return TaxStatusClass(*tax_status.values())

def get_account_info(conn, user_token, account_hash, account_name):
    c = conn.execute('SELECT Description, TaxGroup FROM AccountInfoMap WHERE AccountID = ?', (account_hash,))
    ret = c.fetchone()

    tax_status = None
    description = None
    info = None

    if ret is not None:
        tax_status = ret[1]
        description = decrypt_account_description(user_token,
                                                  account_name,
                                                  ret[0],
                                                  conn=conn)
        info = (tax_status, description)

    return info

class Session:
    def __init__(self, user_token, filename, taxable_credit = None, tax_deferred_credit = None):
        self.__user_token = user_token
        self.__account_info = {}

        account_entries = parse_file(filename)
        self.__securities_db = SecurityDatabase(account_entries)
        self.__account_target = AccountTarget(user_token, self.__securities_db)
        self.__rebalancer = Rebalancer(self.__securities_db, self.__account_target)

        from multiprocessing import Pool
        p = Pool()

        with create_db_conn() as conn:
            salt = get_user_salt(conn, user_token)
            hash_fun = partial(hash_account_name, self.__user_token, salt=salt)
            account_names = list(set(map(lambda x: x.account_name, account_entries)))
            account_hashes = list(p.map(hash_fun, account_names))

            self.__account_hashes = dict(zip(account_names, account_hashes))

            TaxStatus = create_tax_status(conn)
            self.__portfolio = Portfolio(self.__securities_db, TaxStatus)

            for account_entry in account_entries:
                if self.__securities_db.contains_symbol(account_entry.symbol):
                    account_info = self.__get_account_info(conn, account_entry.account_name)
                    if account_info is not None:
                        (tax_status, description) = account_info

                        current_value = account_entry.current_value

                        if account_entry.is_sweep:
                            if taxable_credit is not None and \
                               tax_status == TaxStatus.TAXABLE:
                                current_value += taxable_credit
                            elif tax_deferred_credit is not None and \
                                 tax_status == TaxStatus.TAX_DEFERRED:
                                current_value += tax_deferred_credit

                        self.__portfolio.add_position(description,
                                                      tax_status,
                                                      account_entry.symbol,
                                                      current_value)

    def get_portfolio(self):
        return self.__portfolio

    def get_rebalancer(self):
        return self.__rebalancer

    def get_account_target(self):
        return self.__account_target

    def __get_account_info(self, conn, account_name):
        if account_name not in self.__account_info:
            account_hash = self.__get_account_name_hash(conn, account_name)

            info = get_account_info(conn, self.__user_token, account_hash, account_name)
            self.__account_info[account_name] = info

        return self.__account_info[account_name]

    def __get_account_name_hash(self, conn, account_name):
        if account_name not in self.__account_hashes:
            self.__account_hashes[account_name] = hash_account_name(conn,
                                                                    self.__user_token,
                                                                    account_name)

        return self.__account_hashes[account_name]
