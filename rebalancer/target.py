from collections import namedtuple, defaultdict
from decimal import Decimal

from .crypto import hash_user_token_with_salt
from .db import Database
from .utils import round_cents

DEFAULT = "DEFAULT"

def get_asset_targets_by_id(database, user_token):
    ret = {}
    for (asset, target, target_type) in database.get_asset_targets(user_token):
        value = None
        if target_type == "Percent" or target_type == "Percent Remainder":
            value = (Decimal(target) / 1000).quantize(Decimal('0.001'))
        elif target_type == "Dollars":
            value = round_cents(Decimal(target))
        else:
            raise KeyError("Invalid TargetType: %s" % (target_type))

        ret[asset] = (value, target_type)

    return ret

def get_asset_targets(database, user_token):
    ret = get_asset_targets_by_id(database, user_token)
    if len(ret) == 0:
        ret = get_asset_targets_by_id(database, DEFAULT)

    return ret

def get_asset_tax_affinity_by_id(database, user_token):
    affinity = defaultdict(list)
    for (asset, tax_group) in database.get_asset_tax_affinity(user_token):
        affinity[asset].append(tax_group)

    return dict(affinity.items())

def get_asset_tax_affinity(database, user_token):
    ret = get_asset_tax_affinity_by_id(database, user_token)
    if len(ret) == 0:
        ret = get_asset_tax_affinity_by_id(database, DEFAULT)

    return ret

def get_tax_group_asset_affinity_by_id(database, user_token):
    affinity = defaultdict(list)
    for (asset, tax_group) in database.get_tax_group_asset_affinity(user_token):
        affinity[tax_group].append(asset)

    return dict(affinity.items())

def get_tax_group_asset_affinity(database, user_token):
    ret = get_tax_group_asset_affinity_by_id(database, user_token)
    if len(ret) == 0:
        ret = get_tax_group_asset_affinity_by_id(database, DEFAULT)

    return ret

def get_asset_sales_mask_by_id(database, user_token):
    return set(database.get_asset_sales_mask(user_token))

def get_asset_sales_mask(database, user_token):
    ret = get_asset_sales_mask_by_id(database, user_token)
    if len(ret) == 0:
        ret = get_asset_sales_mask_by_id(database, DEFAULT)

    return ret

class AccountTarget:
    def __init__(self, user_token, security_db, database):
        self.__security_db = security_db
        self.__init_from_db(user_token, security_db, database)

    def __init_from_db(self, user_token, security_db, db):
        asset_targets = get_asset_targets(db, user_token)
        asset_tax_affinity = get_asset_tax_affinity(db, user_token)
        tax_group_asset_affinity = get_tax_group_asset_affinity(db, user_token)

        self.__asset_targets = asset_targets
        self.__asset_tax_affinity = asset_tax_affinity
        self.__tax_group_asset_affinity = tax_group_asset_affinity
        self.__asset_sales_mask = get_asset_sales_mask(db, user_token)

    def get_asset_targets(self):
        return self.__asset_targets.copy()

    def get_target_asset_percentages(self, portfolio):
        current_value = portfolio.current_value()

        remainder_percentages = {}
        ret = {}
        for (asset, (target, target_type)) in self.__asset_targets.items():
            if target_type == "Percent":
                ret[asset] = target
            elif target_type == "Dollars":
                ret[asset] = target / current_value
            elif target_type == "Percent Remainder":
                remainder_percentages[asset] = target
            else:
                raise KeyError("Invalid TargetType: %s" % (target_type))

        if len(remainder_percentages) > 0:
            remainder_percent = Decimal(1.0) - sum(ret.values())
            for (asset, target) in remainder_percentages.items():
                ret[asset] = target * remainder_percent

        return ret

    def get_target_asset_group_percentages(self, portfolio):
        target_asset_percentages = self.get_target_asset_percentages(portfolio)

        ret = defaultdict(Decimal)
        for (asset, percent) in target_asset_percentages.items():
            asset_group = self.__security_db.get_asset_group_for_asset(asset)
            ret[asset_group] += percent

        return dict(ret.items())

    def get_target_asset_values(self, portfolio):
        current_value = portfolio.current_value()

        remainder_percentages = {}
        targets = {}
        for (asset, (target, target_type)) in self.__asset_targets.items():
            if target_type == "Percent":
                targets[asset] = round_cents(target * current_value)
            elif target_type == "Dollars":
                targets[asset] = target
            elif target_type == "Percent Remainder":
                remainder_percentages[asset] = target
            else:
                raise KeyError("Invalid TargetType: %s" % (target_type))

        if len(remainder_percentages) > 0:
            remainder_value = current_value - sum(targets.values())
            for (asset, target) in remainder_percentages.items():
                targets[asset] = round_cents(target * remainder_value)

        return targets

    def get_target_asset_group_values(self, portfolio):
        targets = defaultdict(Decimal)
        target_asset_values = self.get_target_asset_values(portfolio)

        total_value = portfolio.current_value()
        for (asset, value) in portfolio.items():
            target = target_asset_values[asset]
            asset_group = self.__security_db.get_asset_group_for_asset(asset)
            targets[asset_group] += target

        return dict(targets.items())

    def get_actual_asset_group_values(self, portfolio):
        targets = defaultdict(Decimal)

        for (asset, value) in portfolio.items():
            asset_group = self.__security_db.get_asset_group_for_asset(asset)
            targets[asset_group] += value

        return dict(targets.items())

    def get_asset_tax_affinity(self, asset):
        return self.__asset_tax_affinity[asset].copy()

    def get_tax_group_asset_affinity(self, tax_group):
        return self.__tax_group_asset_affinity[tax_group].copy()

    def get_asset_sales_mask(self):
        return self.__asset_sales_mask.copy()
