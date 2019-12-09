from collections import namedtuple, defaultdict
from decimal import Decimal

from .crypto import hash_user_token_with_salt
from .db import Database
from .utils import round_cents, to_enum_name

DEFAULT = "DEFAULT"

def get_asset_targets_by_id(database, target_types, user_token):
    ret = {}
    for (asset, target, target_type) in database.get_asset_targets(user_token):
        value = None
        if target_type == target_types.PERCENT or \
           target_type == target_types.PERCENT_REMAINDER:
            value = (Decimal(target) / 1000).quantize(Decimal('0.001'))
        elif target_type == target_types.DOLLARS:
            value = round_cents(Decimal(target))
        else:
            raise KeyError("Invalid TargetType: %s" % (target_type))

        ret[asset] = (value, target_type)

    return ret

def get_asset_targets(database, target_types, user_token):
    ret = get_asset_targets_by_id(database, target_types, user_token)
    if len(ret) == 0:
        ret = get_asset_targets_by_id(database, target_types, DEFAULT)

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
        target_types = {}
        self.__target_type_abbreviations = {}
        for (name, abbreviation, _) in db.get_target_types():
            target_types[to_enum_name(name)] = name
            self.__target_type_abbreviations[name] = abbreviation

        TargetTypesClass = namedtuple('TargetTypesClass', ' '.join(target_types.keys()))
        self.TargetTypes = TargetTypesClass(*target_types.values())

        asset_targets = get_asset_targets(db, self.TargetTypes, user_token)
        asset_tax_affinity = get_asset_tax_affinity(db, user_token)
        tax_group_asset_affinity = get_tax_group_asset_affinity(db, user_token)

        security_db.ensure_have_current_prices(asset_targets.keys(), db)

        self.__asset_targets = asset_targets
        self.__asset_tax_affinity = asset_tax_affinity
        self.__tax_group_asset_affinity = tax_group_asset_affinity
        self.__asset_sales_mask = get_asset_sales_mask(db, user_token)

    def get_target_type_abbreviation(self, target_type):
        return self.__target_type_abbreviations[target_type]

    def get_asset_targets(self):
        return self.__asset_targets.copy()

    def get_target_asset_percentages(self, portfolio):
        current_value = portfolio.current_value()
        max_percent = Decimal(1.0)

        remainder_percentages = {}
        ret = defaultdict(Decimal)
        for (asset, (target, target_type)) in self.__asset_targets.items():
            if target_type == self.TargetTypes.PERCENT:
                ret[asset] = min(target, max_percent)
                max_percent -= target
            elif target_type == self.TargetTypes.DOLLARS:
                percent = min(target / current_value, max_percent)
                ret[asset] = percent
                max_percent -= percent
            elif target_type == self.TargetTypes.PERCENT_REMAINDER:
                remainder_percentages[asset] = target
            else:
                raise KeyError("Invalid TargetType: %s" % (target_type))

        remainder_percent = Decimal(1.0) - sum(ret.values())
        while remainder_percent > Decimal(0.0) and len(remainder_percentages) > 0:
            for (asset, target) in remainder_percentages.items():
                percent = min(target * remainder_percent, max_percent)
                ret[asset] += percent
                max_percent -= percent

            remainder_percent = Decimal(1.0) - sum(ret.values())

        assert sum(ret.values()) == Decimal(1.0), "Target Asset Percentages must add to 1.0"

        return ret

    def get_target_asset_group_percentages(self, portfolio):
        target_asset_percentages = self.get_target_asset_percentages(portfolio)

        ret = defaultdict(Decimal)
        for (asset, percent) in target_asset_percentages.items():
            asset_group = self.__security_db.get_asset_group_for_asset(asset)
            ret[asset_group] += percent

        return ret

    def get_target_asset_values(self, portfolio):
        current_value = portfolio.current_value()
        max_amount = current_value

        remainder_percentages = {}
        targets = defaultdict(Decimal)
        for (asset, (target, target_type)) in self.__asset_targets.items():
            if target_type == self.TargetTypes.PERCENT:
                amount = min(round_cents(target * current_value), max_amount)
                targets[asset] = amount
                max_amount -= amount
            elif target_type == self.TargetTypes.DOLLARS:
                amount = min(target, max_amount)
                targets[asset] = amount
                max_amount -= amount
            elif target_type == self.TargetTypes.PERCENT_REMAINDER:
                remainder_percentages[asset] = target
            else:
                raise KeyError("Invalid TargetType: %s" % (target_type))

        remainder_value = current_value - round_cents(sum(targets.values()))
        while remainder_value > Decimal(0) and len(remainder_percentages) > 0:
            for (asset, target) in remainder_percentages.items():
                amount = min(round_cents(target * remainder_value), max_amount)
                targets[asset] += amount
                max_amount -= amount

            remainder_value = current_value - round_cents(sum(targets.values()))

        assert sum(targets.values()) == current_value, "Target Asset Values must add to current value"

        return targets

    def get_target_asset_group_values(self, portfolio):
        targets = defaultdict(Decimal)
        target_asset_values = self.get_target_asset_values(portfolio)

        total_value = portfolio.current_value()
        for (asset, _) in self.__asset_targets.items():
            target = target_asset_values[asset]
            asset_group = self.__security_db.get_asset_group_for_asset(asset)
            targets[asset_group] += target

        return targets

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
