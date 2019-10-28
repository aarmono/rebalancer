from collections import namedtuple, defaultdict
from decimal import Decimal

from .utils import to_enum_name, is_mutual_fund, round_cents
from .db import Database

def get_current_price_from_web(symbol, service_key):
    import urllib.request
    import urllib.parse
    import json

    parms = {
        'function' : 'GLOBAL_QUOTE',
        'symbol'   : symbol,
        'apikey'   : service_key
    }
    data = urllib.parse.urlencode(parms)
    url = "https://www.alphavantage.co/query?%s" % data
    with urllib.request.urlopen(url) as f:
        j = json.loads(f.read().decode('ascii'))
        return round_cents(Decimal(j['Global Quote']['05. price']))

class SecurityDatabase:
    def __init__(self, account_entries = None, database = None, quote_key = None):
        self.__quote_key = quote_key

        if account_entries is not None:
            self.__current_prices = dict([(entry.symbol, entry.share_price) for entry in account_entries])

        if database is None:
            with Database() as db:
                self.__init_from_db(db)
        else:
            self.__init_from_db(database)

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
        if self.get_asset_class(symbol) == self.Assets.CASH:
            return Decimal(1.0)
        elif self.__quote_key is not None and symbol not in self.__current_prices:
            current_price = get_current_price_from_web(symbol, self.__quote_key)
            self.__current_prices[symbol] = current_price

        return self.__current_prices[symbol]

    def supports_fractional_shares(self, symbol):
        return is_mutual_fund(symbol) or \
               self.get_asset_group(symbol) == self.AssetGroups.CASH

    def get_reference_security(self, asset):
        return self.__default_securities[asset]

    def __init_from_db(self, db):
        self.__create_securities(db)
        self.__create_assets(db)
        self.__create_asset_groups(db)
        self.__create_default_securities(db)

    def __create_securities(self, database):
        asset_classes = {}
        asset_groups = {}
        security_asset_groups = {}
        asset_securities = defaultdict(list)
        for security in database.get_securities():
            asset_classes[security.symbol] = security.asset
            asset_groups[security.asset] = security.asset_group
            security_asset_groups[security.symbol] = security.asset_group
            asset_securities[security.asset].append(security.symbol)

        self.__asset_groups = asset_groups
        self.__asset_classes = asset_classes
        self.__security_asset_groups = security_asset_groups
        self.__asset_securities = asset_securities

    def __create_default_securities(self, database):
        self.__default_securities = dict(database.get_default_securities())

    def __create_assets(self, database):
        assets = {}
        for (abbrev, _) in database.get_asset_abbreviations():
            assets[to_enum_name(abbrev)] = abbrev

        AssetsClass = namedtuple('AssetsClass', ' '.join(assets.keys()))
        self.Assets = AssetsClass(*assets.values())

    def __create_asset_groups(self, database):
        asset_groups = {}
        for (name, _) in database.get_asset_groups():
            asset_groups[to_enum_name(name)] = name

        AssetGroupsClass = namedtuple('AssetGroupsClass',
                                      ' '.join(asset_groups.keys()))
        self.AssetGroups = AssetGroupsClass(*asset_groups.values())
