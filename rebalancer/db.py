from os import path
from sqlite3 import connect
from decimal import Decimal
from collections import namedtuple

from .crypto import hash_user_token, hash_account_name, hash_user_token_with_salt
from .crypto import encrypt_account_description, decrypt_account_description, get_description_key

def create_db_conn(database_path):
    conn = connect(database_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn

AssetTarget = namedtuple('AssetTarget', 'asset target_deci_percent')
AssetTaxGroup = namedtuple('AssetTaxGroup', 'asset tax_group')
Security = namedtuple('Security', 'symbol asset asset_group')
AccountInfo = namedtuple('AccountInfo', 'description tax_status')
IDEntry = namedtuple('IDEntry', 'name id')
DefaultSecurity = namedtuple('DefaultSecurity', 'asset symbol')

AssetAffinity = namedtuple('AssetAffinity', 'asset tax_group priority')


DB_UPGRADE_FILENAMES = [
    "rebalancer_v1.sql"
]

CURRENT_DB_VERSION = 1

class Database:
    def __init__(self):
        this_file_path = path.abspath(__file__)
        this_dir = path.dirname(this_file_path)
        database_path = path.join(this_dir, "rebalance.db")

        self.__conn = create_db_conn(database_path)

        db_version = self.get_db_version()
        while db_version < len(DB_UPGRADE_FILENAMES):
            script_path = path.join(this_dir, DB_UPGRADE_FILENAMES[db_version])
            with open(script_path, "r") as f:
                self.__conn.executescript(f.read())
                self.__conn.commit()

            db_version = self.get_db_version()

        self.__hashed_tokens_system = {}
        self.__hashed_tokens_user = {}
        self.__account_hashes = {}
        self.__account_keys = {}

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

    def __get_user_hash_system_salt(self, user_token):
        if user_token not in self.__hashed_tokens_system:
            hashed_token = hash_user_token(user_token)
            self.__hashed_tokens_system[user_token] = hashed_token

        return self.__hashed_tokens_system[user_token]

    def __get_user_hash_user_salt(self, user_token):
        if user_token not in self.__hashed_tokens_user:
            salt = self.get_user_salt(user_token)
            salted_token = hash_user_token_with_salt(user_token, salt)
            self.__hashed_tokens_user[user_token] = salted_token

        return self.__hashed_tokens_user[user_token]

    def __get_account_hash(self, user_token, account):
        key = (user_token, account)
        if key not in self.__account_hashes:
            salt = self.get_user_salt(user_token)
            account_hash = hash_account_name(user_token, account, salt)

            self.__account_hashes[key] = account_hash

        return self.__account_hashes[key]

    def __get_account_key(self, user_token, account):
        key = (user_token, account)
        if key not in self.__account_keys:
            salt = self.get_user_salt(user_token)
            description_key = get_description_key(user_token, account, salt)

            self.__account_keys[key] = description_key

        return self.__account_keys[key]

    def get_db_version(self):
        return self.__return_one(lambda x: x[0], "PRAGMA user_version")

    def get_asset_targets(self, user_token):
        user_hash = self.__get_user_hash_user_salt(user_token)
        cmd = "SELECT Asset, TargetDeciPercent FROM AssetTargetsMap WHERE User == ?"
        return self.__return_iter(AssetTarget._make, cmd, user_hash)

    def set_asset_targets(self, user_token, asset_targets):
        user_hash = self.__get_user_hash_user_salt(user_token)
        self.__return_one(''.join,
                          "DELETE FROM Targets WHERE User == ?",
                          user_hash)

        for (asset, target_deci_percent) in asset_targets:
            cmd = "INSERT INTO Targets (User, AssetID, TargetDeciPercent) VALUES (?, (SELECT ID FROM Assets WHERE Abbreviation == ?), ?)"
            self.__return_one(str, cmd, user_hash, asset, target_deci_percent)

    def get_asset_tax_affinity(self, user_token):
        user_hash = self.__get_user_hash_user_salt(user_token)
        cmd = "SELECT Asset, TaxGroup FROM AssetAffinitiesMap WHERE User == ? ORDER BY Asset, Priority"
        return self.__return_iter(AssetTaxGroup._make, cmd, user_hash)

    def get_tax_group_asset_affinity(self, user_token):
        user_hash = self.__get_user_hash_user_salt(user_token)
        cmd = "SELECT Asset, TaxGroup FROM AssetAffinitiesMap WHERE User == ? ORDER BY TaxGroup, Priority"
        return self.__return_iter(AssetTaxGroup._make, cmd, user_hash)

    def get_securities(self):
        cmd = "SELECT Symbol, Asset, AssetGroup from SecuritiesMap"
        return self.__return_iter(Security._make, cmd)

    def get_assets(self):
        cmd = "SELECT Asset, AssetGroup FROM AssetGroupsMap"
        return self.__return_iter(tuple, cmd)

    def get_asset_abbreviations(self):
        cmd = "SELECT Abbreviation, ID from Assets"
        return self.__return_iter(IDEntry._make, cmd)

    def get_asset_groups(self):
        cmd = "SELECT Name, ID from AssetGroups"
        return self.__return_iter(IDEntry._make, cmd)

    def get_default_securities(self):
        cmd = "SELECT Asset, Symbol FROM DefaultSecurities"
        return self.__return_iter(DefaultSecurity._make, cmd)

    def set_default_security(self, symbol):
        cmd = "UPDATE Securities SET IsDefault = 1 WHERE Symbol == ?"
        self.__return_one(str, cmd, symbol)

    def get_tax_groups(self):
        cmd = "SELECT Name, ID FROM TaxGroups"
        return self.__return_iter(IDEntry._make, cmd)

    def get_user_salt(self, user_token):
        user_hash = self.__get_user_hash_system_salt(user_token)

        cmd = "SELECT Salt FROM UserSalts WHERE User = ?"
        return self.__return_one(''.join, cmd, user_hash)

    def add_user(self, user_token):
        user_hash = self.__get_user_hash_system_salt(user_token)

        cmd = "INSERT INTO UserSalts (User) VALUES (?)"
        self.__return_one(str, cmd, user_hash)

    def add_account(self, user_token, account, description, tax_group):
        hashed_account = self.__get_account_hash(user_token, account)

        encrypted_description = None
        if len(description) > 0:
            description_key = self.__get_account_key(user_token, account)
            encrypted_description = encrypt_account_description(description_key,
                                                                description)

        cmd = "REPLACE INTO Accounts (ID, Description, TaxGroupID) VALUES (?, ?, (SELECT ID From TaxGroups WHERE Name == ?))"
        self.__return_one(str,
                          cmd,
                          hashed_account,
                          encrypted_description,
                          tax_group)

    def delete_account(self, user_token, account):
        hashed_account = self.__get_account_hash(user_token, account)

        del self.__account_hashes[(user_token, account)]

        cmd = "DELETE FROM Accounts WHERE ID == ?"
        self.__return_one(str, cmd, hashed_account)


    def get_account_info(self, user_token, account):
        hashed_account = self.__get_account_hash(user_token, account)

        cmd = "SELECT Description, TaxGroup FROM AccountInfoMap WHERE AccountID = ?"
        result = self.__return_one(tuple, cmd, hashed_account)
        if result is not None:
            (description, tax_group) = result

            if description is not None:
                description_key = self.__get_account_key(user_token, account)
                description = decrypt_account_description(description_key,
                                                          description)

            return AccountInfo(description, tax_group)
        else:
            return None

    def set_asset_affinities(self, user_token, asset_affinities, asset_sales_mask):
        salted_token = self.__get_user_hash_user_salt(user_token)

        self.__return_one(''.join,
                          "DELETE FROM AssetAffinities WHERE User == ?",
                          salted_token)

        for affinity in asset_affinities:
            asset_tax_group = AssetTaxGroup(affinity.asset, affinity.tax_group)
            can_sell = 0 if asset_tax_group in asset_sales_mask else 1
            cmd = "INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority, CanSell) VALUES (?, (SELECT ID FROM TaxGroups WHERE Name == ?), (SELECT ID FROM Assets WHERE Abbreviation == ?), ?, ?)"
            self.__return_one(''.join,
                              cmd,
                              salted_token,
                              affinity.tax_group,
                              affinity.asset,
                              affinity.priority,
                              can_sell)

    def get_asset_sales_mask(self, user_token):
        salted_token = self.__get_user_hash_user_salt(user_token)

        cmd = "SELECT Asset, TaxGroup FROM AssetSalesMask WHERE User == ?"

        return self.__return_iter(AssetTaxGroup._make, cmd, salted_token)

    def add_symbol(self, symbol, asset, is_default = False):
        cmd = "INSERT INTO Securities (Symbol, AssetID, IsDefault) VALUES (?, (SELECT ID FROM Assets WHERE Abbreviation == ?), ?)"
        self.__return_one(str, cmd, symbol, asset, is_default)

    def delete_symbol(self, symbol):
        cmd = "DELETE FROM Securities WHERE Symbol == ?"
        self.__return_one(str, cmd, symbol)

    def add_asset(self, asset, asset_group):
        cmd = "INSERT INTO Assets (Abbreviation, AssetGroupID) VALUES (?, (SELECT ID FROM AssetGroups WHERE Name == ?))"
        self.__return_one(str, cmd, asset, asset_group)

    def delete_asset(self, asset):
        cmd = "DELETE FROM Assets WHERE Abbreviation == ?"
        self.__return_one(str, cmd, asset)

    def add_asset_group(self, asset_group):
        cmd = "INSERT INTO AssetGroups (Name) VALUES (?)"
        self.__return_one(str, cmd, asset_group)

    def delete_asset_group(self, asset_group):
        cmd = "DELETE FROM AssetGroups WHERE Name == ?"
        self.__return_one(str, cmd, asset_group)

    def commit(self):
        self.__conn.commit()
