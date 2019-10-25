from collections import namedtuple, defaultdict
from decimal import Decimal

from .crypto import hash_user_token
from .db import create_db_conn
from .utils import round_cents

def get_asset_targets_by_id(conn, user_hash):
    ret = {}
    user = "DEFAULT" if user_hash is None else user_hash
    for (asset, target) in conn.execute("SELECT Asset, TargetDeciPercent FROM AssetTargetsMap WHERE User == ?", (user,)):
        ret[asset] = (Decimal(target) / 1000).quantize(Decimal('0.001'))

    return ret

def get_asset_targets(conn, user_hash):
    ret = get_asset_targets_by_id(conn, user_hash)
    if len(ret) == 0:
        ret = get_asset_targets_by_id(conn, None)

    return ret

def get_asset_tax_affinity_by_id(conn, user_hash):
    affinity = defaultdict(list)
    user = "DEFAULT" if user_hash is None else user_hash
    for (asset, tax_group) in conn.execute("SELECT Asset, TaxGroup FROM AssetAffinitiesMap WHERE User == ? ORDER BY Asset, Priority", (user,)):
        affinity[asset].append(tax_group)

    return dict(affinity.items())

def get_asset_tax_affinity(conn, user_hash):
    ret = get_asset_tax_affinity_by_id(conn, user_hash)
    if len(ret) == 0:
        ret = get_asset_tax_affinity_by_id(conn, None)

    return ret

def get_tax_group_asset_affinity_by_id(conn, user_hash):
    affinity = defaultdict(list)
    user = "DEFAULT" if user_hash is None else user_hash
    for (asset, tax_group) in conn.execute("SELECT Asset, TaxGroup FROM AssetAffinitiesMap WHERE User == ? ORDER BY TaxGroup, Priority", (user,)):
        affinity[tax_group].append(asset)

    return dict(affinity.items())

def get_tax_group_asset_affinity(conn, user_hash):
    ret = get_tax_group_asset_affinity_by_id(conn, user_hash)
    if len(ret) == 0:
        ret = get_tax_group_asset_affinity_by_id(conn, None)

    return ret

class AccountTarget:
    def __init__(self, user_token, security_db):
        self.__security_db = security_db

        user_hash = hash_user_token(user_token)
        with create_db_conn() as conn:
            asset_targets = get_asset_targets(conn, user_hash)
            asset_tax_affinity = get_asset_tax_affinity(conn, user_hash)
            tax_group_asset_affinity = get_tax_group_asset_affinity(conn, user_hash)

            asset_group_targets = defaultdict(Decimal)
            for (asset, target) in asset_targets.items():
                asset_group = security_db.get_asset_group_for_asset(asset)
                asset_group_targets[asset_group] += target

            self.__asset_targets = asset_targets
            self.__asset_tax_affinity = asset_tax_affinity
            self.__tax_group_asset_affinity = tax_group_asset_affinity
            self.__asset_group_targets = dict(asset_group_targets.items())

    def get_target_asset_percentages(self):
        return self.__asset_targets.copy()

    def get_target_asset_group_percentages(self):
        return self.__asset_group_targets.copy()

    def get_target_asset_values(self, portfolio):
        targets = {}

        total_value = portfolio.current_value()
        for (asset, value) in portfolio.items():
            target = self.__asset_targets[asset] * total_value
            targets[asset] = round_cents(target)

        return targets

    def get_target_asset_group_values(self, portfolio):
        targets = defaultdict(Decimal)

        total_value = portfolio.current_value()
        for (asset, value) in portfolio.items():
            target = self.__asset_targets[asset] * total_value
            asset_group = self.__security_db.get_asset_group_for_asset(asset)
            targets[asset_group] += round_cents(target)

        return dict(targets.items())

    def get_actual_asset_group_values(self, portfolio):
        targets = defaultdict(Decimal)

        for (asset, value) in portfolio.items():
            asset_group = self.__security_db.get_asset_group_for_asset(asset)
            targets[asset_group] += value

        return dict(targets.items())

    def get_asset_tax_affinity(self, asset):
        return self.__asset_tax_affinity[asset]

    def get_tax_group_asset_affinity(self, tax_group):
        return self.__tax_group_asset_affinity[tax_group]
