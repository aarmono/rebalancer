from decimal import Decimal
from collections import defaultdict

from itertools import chain
from functools import partial, cmp_to_key

from .utils import compute_percent_difference

class RebalanceMode:
    FULL            = "Rebalance everything"
    NO_SELL_TAXABLE = "Rebalance without selling in Taxable"
    NO_SELL         = "Rebalance without selling"

class Rebalancer:
    def __init__(self, security_db, account_target):
        self.__security_db = security_db
        self.__account_target = account_target

    def __compare_symbols(self, symbol_keys, x, y):
        CASH = self.__security_db.Assets.CASH

        if x == CASH and y != CASH:
            return 1
        elif x != CASH and y == CASH:
            return -1
        elif symbol_keys[x][0] == symbol_keys[y][0]:
            if symbol_keys[x][1] < symbol_keys[y][1]:
                return -1
            elif symbol_keys[x][1] > symbol_keys[y][1]:
                return 1
            else:
                return 0
        elif symbol_keys[x][0] < symbol_keys[y][0]:
            return -1
        else:
            return 1

    def __prioritize_assets_by_difference(self, portfolio, reverse=False):
        group_targets = self.__account_target.get_target_asset_group_values(portfolio)
        target_values = self.__account_target.get_target_asset_values(portfolio)
        group_actuals = self.__account_target.get_actual_asset_group_values(portfolio)

        group_differences = {}
        for (group, value) in group_targets.items():
            group_differences[group] = group_actuals.get(group, Decimal(0.0)) - value

        for (group, value) in group_actuals.items():
            group_differences[group] = value - group_targets.get(group, Decimal(0.0))

        symbol_keys = {}
        for (asset, value) in portfolio.items():
            group = self.__security_db.get_asset_group_for_asset(asset)

            difference = group_differences[group]
            percent_difference = compute_percent_difference(value, target_values[asset])

            symbol_keys[asset] = (difference, percent_difference)

        return sorted(symbol_keys.keys(),
                      key=cmp_to_key(partial(self.__compare_symbols, symbol_keys)),
                      reverse=reverse)

    def __prioritize_assets_by_target_value(self, portfolio, reverse=False):
        target_asset_values = self.__account_target.get_target_asset_values(portfolio)

        def cmp_fun(a, b):
            a_affin = self.__account_target.get_asset_tax_affinity(a)[0]
            b_affin = self.__account_target.get_asset_tax_affinity(b)[0]
            assets_by_tax_status = portfolio.assets_by_tax_status()
            a_val = assets_by_tax_status[a_affin].current_value()
            b_val = assets_by_tax_status[b_affin].current_value()

            a_ratio = target_asset_values[a] / a_val
            b_ratio = target_asset_values[b] / b_val

            # Prioritize assets which are a higher percentage of their
            # target account space
            if a_ratio < b_ratio:
                return 1
            elif target_asset_values[a] > target_asset_values[b]:
                return -1
            else:
                # Check if the assets have the same primary tax affinity
                if a_affin != b_affin:
                    # prioritize assets with affinities whose accounts have
                    # lower total capacity
                    if a_val < b_val:
                        return -1
                    elif b_val > a_val:
                        return 1
                    else:
                        return 0
                else:
                    assets = self.__account_target.get_tax_group_asset_affinity(a_affin)
                    a_idx = assets.index(a)
                    b_idx = assets.index(b)
                    # Prioritize assets with a higher priority within the
                    # tax group
                    if a_idx > b_idx:
                        return 1
                    elif a_idx < b_idx:
                        return -1
                    else:
                        return 0

        return sorted(portfolio.keys(),
                      key=cmp_to_key(cmp_fun),
                      reverse=reverse)

    def compute_target_asset_values(self, portfolio, rebalance_mode):
        rebalance_full = rebalance_mode == RebalanceMode.FULL
        priority_fun = self.__prioritize_assets_by_target_value if rebalance_full else \
                       self.__prioritize_assets_by_difference

        seed_tax_groups = []
        if rebalance_mode == RebalanceMode.NO_SELL_TAXABLE:
            seed_tax_groups = [portfolio.TaxStatus.TAXABLE]
        elif rebalance_mode == RebalanceMode.NO_SELL:
            seed_tax_groups = portfolio.assets_by_tax_status().keys()

        return self.__compute_target_asset_values_parameterized(portfolio,
                                                                priority_fun,
                                                                seed_tax_groups)

    def __get_assets_with_top_affinity(self, asset_affinities, tax_status):
        CASH = self.__security_db.Assets.CASH
        return list(map(lambda y: y[0],
                    filter(lambda x: x[0] != CASH and x[1][0] == tax_status,
                           asset_affinities)))

    def __compute_target_asset_values_parameterized(self,
                                                    portfolio,
                                                    priority_fun,
                                                    seed_tax_groups):
        target_asset_group_values = self.__account_target.get_target_asset_group_values(portfolio)
        target_asset_values = self.__account_target.get_target_asset_values(portfolio)

        asset_affinities = [(x, self.__account_target.get_asset_tax_affinity(x)) for x in priority_fun(portfolio)]

        current_asset_values = portfolio.assets_by_tax_status()
        tax_status_amounts = dict([(x, y.current_value()) for (x, y) in current_asset_values.items()])

        targets = defaultdict(partial(defaultdict, Decimal))
        for tax_status in seed_tax_groups:
            account_group = current_asset_values[tax_status]
            for (asset, value) in account_group.items():
                CASH = self.__security_db.Assets.CASH

                group = self.__security_db.get_asset_group_for_asset(asset)
                target_value = Decimal(0.0) if asset == CASH else value
                targets[tax_status][asset] = target_value

                tax_status_amounts[tax_status] -= target_value
                target_asset_group_values[group] = max(Decimal(0.0),
                                                       target_asset_group_values[group] - target_value)
                target_asset_values[asset] = max(Decimal(0.0),
                                                 target_asset_values[asset] - target_value)

        for (asset, affinity_list) in asset_affinities:
            group = self.__security_db.get_asset_group_for_asset(asset)
            for affinity in affinity_list:
                if affinity in tax_status_amounts and tax_status_amounts[affinity] > Decimal(0.0):
                    alloc_amount = min(tax_status_amounts[affinity],
                                       target_asset_values[asset],
                                       target_asset_group_values[group])

                    targets[affinity][asset] += alloc_amount

                    tax_status_amounts[affinity] -= alloc_amount
                    target_asset_group_values[group] -= alloc_amount
                    target_asset_values[asset] -= alloc_amount

                    if target_asset_group_values[group] == Decimal(0.0) or \
                       target_asset_values[asset] == Decimal(0.0):
                        break

        # If there is leftover cash within a tax group, allocate it evenly
        # among assets which have top affinity for that group
        for tax_status in portfolio.assets_by_tax_status().keys():
            tax_status_amount = tax_status_amounts[tax_status]
            if tax_status_amount > Decimal(0.0):
                assets = self.__account_target.get_tax_group_asset_affinity(tax_status)

                # Compute the remainder as a percentage of the total assets in
                # this tax group with affinity to this tax group
                asset_sum = sum(map(lambda x: targets[tax_status][x], assets))
                percent_difference = tax_status_amount / asset_sum

                # Add to each asset with affinity with equal percentage
                for asset in assets:
                    to_add = min(tax_status_amount,
                                 targets[tax_status][asset] * percent_difference)

                    targets[tax_status][asset] += to_add

                    tax_status_amount -= to_add
                    if tax_status_amount <= Decimal(0.0):
                        break

        return targets
