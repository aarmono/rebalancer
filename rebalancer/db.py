from os import path
from sqlite3 import connect
from decimal import Decimal
from collections import namedtuple

from .crypto import hash_user_token, hash_account_name
from .crypto import encrypt_account_description, decrypt_account_description

def create_db_conn():
    this_file_path = path.abspath(__file__)
    this_dir = path.dirname(this_file_path)
    database_path = path.join(this_dir, "rebalance.db")

    conn = connect(database_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn

def get_user_hash_from_kwargs(kwargs):
    user_hash = None
    if 'user_hash' in kwargs:
        user_hash = kwargs['user_hash']
    else:
        user_hash = hash_user_token(kwargs['user_token'])

    return user_hash

AssetTarget = namedtuple('AssetTarget', 'asset target_deci_percent')
AssetTaxGroup = namedtuple('AssetTaxGroup', 'asset tax_group')
Security = namedtuple('Security', 'symbol asset asset_group')
AccountInfo = namedtuple('AccountInfo', 'description tax_status')

class Database:
    def __init__(self):
        self.__conn = create_db_conn()

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.__conn.close()

    def __return_iter(self, result_type, cmd, *args):
        cur = self.__conn.execute(cmd, args)
        for row in map(result_type, cur.fetchall()):
            yield row

    def __return_one(self, result_type, cmd, *args):
        cur = self.__conn.execute(cmd, args)
        row = cur.fetchone()

        return None if row is None else result_type(row)

    def get_asset_targets(self, user_hash):
        cmd = "SELECT Asset, TargetDeciPercent FROM AssetTargetsMap WHERE User == ?"
        return self.__return_iter(AssetTarget._make, cmd, user_hash)

    def get_asset_tax_affinity(self, user_hash):
        cmd = "SELECT Asset, TaxGroup FROM AssetAffinitiesMap WHERE User == ? ORDER BY Asset, Priority"
        return self.__return_iter(AssetTaxGroup._make, cmd, user_hash)

    def get_tax_group_asset_affinity(self, user_hash):
        cmd = "SELECT Asset, TaxGroup FROM AssetAffinitiesMap WHERE User == ? ORDER BY TaxGroup, Priority"
        return self.__return_iter(AssetTaxGroup._make, cmd, user_hash)

    def get_securities(self):
        cmd = "SELECT Symbol, Asset, AssetGroup from SecuritiesMap"
        return self.__return_iter(Security._make, cmd)

    def get_asset_abbreviations(self):
        cmd = "SELECT Abbreviation from Assets"
        return self.__return_iter(''.join, cmd)

    def get_asset_groups(self):
        cmd = "SELECT Name from AssetGroups"
        return self.__return_iter(''.join, cmd)

    def get_tax_groups(self):
        cmd = "SELECT Name FROM TaxGroups"
        return self.__return_iter(''.join, cmd)

    def get_user_salt(self, **kwargs):
        user_hash = get_user_hash_from_kwargs(kwargs)

        cmd = "SELECT Salt FROM UserSalts WHERE User = ?"
        return self.__return_one(''.join, cmd, user_hash)

    def add_user(self, **kwargs):
        user_hash = get_user_hash_from_kwargs(kwargs)

        cmd = "INSERT INTO UserSalts (User) VALUES (?)"
        self.__return_one(str, cmd, user_hash)

    def add_account(self, user_token, account, description, tax_group_id, salt = None):
        if salt is None:
            salt = self.get_user_salt(user_token = user_token)

        hashed_account = hash_account_name(user_token, account, salt = salt)

        encrypted_description = None
        if len(description) > 0:
            encrypted_description = encrypt_account_description(user_token,
                                                                account,
                                                                description,
                                                                salt = salt)

        cmd = "INSERT INTO Accounts (ID, Description, TaxGroupID) VALUES (?, ?, ?)"
        self.__return_one(str,
                          cmd,
                          hashed_account,
                          encrypted_description,
                          tax_group_id)

    def get_account_info(self, user_token, account, salt = None):
        if salt is None:
            salt = self.get_user_salt(user_token = user_token)

        hashed_account = hash_account_name(user_token, account, salt = salt)

        cmd = "SELECT Description, TaxGroup FROM AccountInfoMap WHERE AccountID = ?"
        result = self.__return_one(tuple, cmd, hashed_account)
        if result is not None:
            (description, tax_group) = result

            if description is not None:
                description = decrypt_account_description(user_token,
                                                          account,
                                                          description,
                                                          salt = salt)

            return AccountInfo(description, tax_group)
        else:
            return None

    def commit(self):
        self.__conn.commit()
