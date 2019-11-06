from decimal import Decimal
from collections import defaultdict, deque

from itertools import chain
from functools import partial, cmp_to_key

from .utils import compute_percent_difference
from .db import AssetTaxGroup

class RebalanceMode:
    FULL            = "Rebalance everything"
    NO_SELL_TAXABLE = "Rebalance without selling in Taxable"
    NO_SELL         = "Rebalance without selling"
    RESHUFFLE       = "Move without rebalancing"

def get_actual_asset_percentages(portfolio):
    current_value = portfolio.current_value()
    ret = {}
    for (asset, value) in portfolio.items():
        ret[asset] = value / current_value

    return ret

class Rebalancer:
    def __init__(self, security_db, account_target):
        self.__security_db = security_db
        self.__account_target = account_target

    def compute_target_asset_values(self, portfolio, rebalance_mode, asset_sales_mask):
        rebalance_full = rebalance_mode == RebalanceMode.FULL

        seed_tax_groups = []
        seed_asset_tax_groups = set(asset_sales_mask)
        current_asset_values = portfolio.assets_by_tax_status()
        if rebalance_mode == RebalanceMode.NO_SELL_TAXABLE:
            seed_tax_groups = [portfolio.TaxStatus.TAXABLE]
        elif rebalance_mode == RebalanceMode.NO_SELL:
            seed_tax_groups = portfolio.assets_by_tax_status().keys()

        for tax_group in seed_tax_groups:
            for asset in current_asset_values[tax_group].keys():
                to_add = AssetTaxGroup(asset, tax_group)
                seed_asset_tax_groups.add(to_add)

        target_asset_group_values = None
        target_asset_values = None
        target_asset_percentages = None

        if rebalance_mode == RebalanceMode.RESHUFFLE:
            target_asset_group_values = self.__account_target.get_actual_asset_group_values(portfolio)
            target_asset_values = dict(portfolio.items())
            target_asset_percentages = get_actual_asset_percentages(portfolio)
        else:
            target_asset_group_values = self.__account_target.get_target_asset_group_values(portfolio)
            target_asset_values = self.__account_target.get_target_asset_values(portfolio)
            target_asset_percentages = self.__account_target.get_target_asset_percentages()

        return self.__compute_target_asset_values_parameterized(portfolio,
                                                                seed_asset_tax_groups,
                                                                target_asset_group_values,
                                                                target_asset_values,
                                                                target_asset_percentages)

    def __compute_target_asset_values_parameterized(self,
                                                    portfolio,
                                                    seed_asset_tax_groups,
                                                    target_asset_group_values,
                                                    target_asset_values,
                                                    target_asset_percentages):
        current_asset_values = portfolio.assets_by_tax_status()
        tax_status_amounts = dict([(x, y.current_value()) for (x, y) in current_asset_values.items()])

        targets = defaultdict(partial(defaultdict, Decimal))
        for (asset, tax_status) in seed_asset_tax_groups:
            value = current_asset_values[tax_status].get(asset, Decimal(0.0))
            CASH = self.__security_db.Assets.CASH

            group = self.__security_db.get_asset_group_for_asset(asset)
            target_value = Decimal(0.0) if asset == CASH else value
            targets[tax_status][asset] = target_value

            tax_status_amounts[tax_status] -= target_value
            target_asset_group_values[group] = max(Decimal(0.0),
                                                   target_asset_group_values[group] - target_value)
            target_asset_values[asset] = max(Decimal(0.0),
                                             target_asset_values[asset] - target_value)

        # Idea for new account allocation policy:
        # 1) Get the asset with the highest priority for each tax group
        # 2) Loop through each account group in ascending order by amount of
        #    "free" space
        # 3) Add as much of the asset as possible to each account group
        # 4) Get the asset with the next highest priority for each tax group
        # 5) Loop through each account group is ascending order by amount of
        #    now "free" space
        def tax_group_asset_affinity_deque(tax_status):
            return (tax_status,
                    deque(self.__account_target.get_tax_group_asset_affinity(tax_status)))

        affinities_by_tax_status = dict(map(tax_group_asset_affinity_deque,
                                            portfolio.assets_by_tax_status().keys()))
        while len(affinities_by_tax_status) > 0:
            sorted_tax_groups = sorted(affinities_by_tax_status.keys(),
                                       key=tax_status_amounts.get)
            for tax_status in sorted_tax_groups:
                affinities = affinities_by_tax_status[tax_status]
                if len(affinities) > 0:
                    asset = affinities.popleft()
                    group = self.__security_db.get_asset_group_for_asset(asset)

                    alloc_amount = min(tax_status_amounts[tax_status],
                                       target_asset_values[asset],
                                       target_asset_group_values[group])

                    targets[tax_status][asset] += alloc_amount

                    tax_status_amounts[tax_status] -= alloc_amount
                    target_asset_group_values[group] -= alloc_amount
                    target_asset_values[asset] -= alloc_amount

                    if tax_status_amounts[tax_status] <= Decimal(0.0):
                        del affinities_by_tax_status[tax_status]

                else:
                    del affinities_by_tax_status[tax_status]

        #If there is leftover cash within a tax group, allocate it based on the
        # target asset percentages normalized for the total percentage of the
        # assets which have affinity for that group
        for tax_status in portfolio.assets_by_tax_status().keys():
            tax_status_amount = tax_status_amounts[tax_status]
            if tax_status_amount > Decimal(0.0):
                assets = self.__account_target.get_tax_group_asset_affinity(tax_status)

                sum_percentage = sum(map(target_asset_percentages.get, assets))

                # Add to each asset with affinity with normalized target percentage
                for asset in assets:
                    target_percentage = target_asset_percentages[asset]
                    normalized_percentage = target_asset_percentages[asset] / sum_percentage

                    to_add = min(tax_status_amounts[tax_status],
                                 tax_status_amount * normalized_percentage)

                    targets[tax_status][asset] += to_add

                    tax_status_amounts[tax_status] -= to_add
                    if tax_status_amounts[tax_status] <= Decimal(0.0):
                        break

        return targets
