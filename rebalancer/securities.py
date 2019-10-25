from collections import namedtuple, defaultdict

from .utils import to_enum_name, is_mutual_fund
from .db import create_db_conn

class SecurityDatabase:
    def __init__(self, account_entries):
        self.__current_prices = dict([(entry.symbol, entry.share_price) for entry in account_entries])

        with create_db_conn() as conn:
            self.__create_securities(conn)
            self.__create_assets(conn)
            self.__create_asset_groups(conn)

    def contains_symbol(self, symbol):
        return symbol in self.__asset_classes

    # US TSM, ex-US TSM, US TBM, etc...
    def get_asset_class(self, symbol):
        return self.__asset_classes[symbol]

    # stock, bond, cash, etc...
    def get_asset_group(self, symbol):
        return self.__security_asset_groups[symbol]

    def get_asset_group_for_asset(self, asset):
        return self.__asset_groups[asset]

    def set_current_price(self, symbol, value):
        self.__current_prices[symbol] = value

    def get_current_price(self, symbol):
        return self.__current_prices[symbol]

    def supports_fractional_shares(self, symbol):
        return is_mutual_fund(symbol) or \
               self.get_asset_group(symbol) == self.AssetGroups.CASH

    def get_reference_security(self, asset):
        for symbol in self.__asset_securities[asset]:
            if is_mutual_fund(symbol) == False and symbol in self.__current_prices:
                return symbol

    def __create_securities(self, conn):
        asset_classes = {}
        asset_groups = {}
        security_asset_groups = {}
        asset_securities = defaultdict(list)
        for (symbol, asset, asset_group) in conn.execute('SELECT Symbol, Asset, AssetGroup from SecuritiesMap'):
            asset_classes[symbol] = asset
            asset_groups[asset] = asset_group
            security_asset_groups[symbol] = asset_group
            asset_securities[asset].append(symbol)

        self.__asset_groups = asset_groups
        self.__asset_classes = asset_classes
        self.__security_asset_groups = security_asset_groups
        self.__asset_securities = asset_securities

    def __create_assets(self, conn):
        assets = {}
        for (abbrev,) in conn.execute('SELECT Abbreviation from Assets'):
            assets[to_enum_name(abbrev)] = abbrev

        AssetsClass = namedtuple('AssetsClass', ' '.join(assets.keys()))
        self.Assets = AssetsClass(*assets.values())

    def __create_asset_groups(self, conn):
        asset_groups = {}
        for (name,) in conn.execute('SELECT Name from AssetGroups'):
            asset_groups[to_enum_name(name)] = name

        AssetGroupsClass = namedtuple('AssetGroupsClass',
                                      ' '.join(asset_groups.keys()))
        self.AssetGroups = AssetGroupsClass(*asset_groups.values())
