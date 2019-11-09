from decimal import Decimal
from collections import defaultdict
from functools import partial, cmp_to_key
from itertools import chain, product

from .utils import round_cents

def compute_asset_differences(actual_assets, target_assets):
    all_asset_names = frozenset(chain(actual_assets.keys(),
                                      target_assets.keys()))

    asset_differences = {}
    for asset in all_asset_names:
        actual_value = actual_assets.get(asset, Decimal(0.0))
        target_value = target_assets.get(asset, Decimal(0.0))

        asset_differences[asset] = actual_value - target_value

    return asset_differences

def compute_transaction_price(transaction):
    transaction_price = Decimal(0.0)
    for (symbol, (shares, buy_price)) in transaction:
        sale_value = shares * buy_price
        transaction_price = transaction_price + sale_value

    return transaction_price

def compute_minimal_remainder_purchase(rebalance, available_funds, max_values):
    rebalance_items = []
    # Construct transactions for each position selling one less share, one
    # more share, and the nominal number of shares
    for (symbol, (shares, sell_price)) in rebalance.items():
        delta = 3
        min_shares = int(max(0, shares - delta))
        max_available_shares = floor(max_values[symbol] / sell_price)
        max_shares = int(min(shares + delta + 1), max_available_shares)
        cur = [(symbol, (x, sell_price)) for x in range(min_shares, max_shares)]

        rebalance_items.append(cur)

    best_transaction_idx = -1
    best_transaction_price = Decimal(0.0)
    # Iterate through all the potential transactions and find the one which
    # most fully utilizes the available funds. The product function will
    # generate a list of all possible transactions from the items we
    # constructed for each position above
    from multiprocessing import Pool
    p = Pool()
    transactions_to_try = list(product(*rebalance_items))
    transaction_prices = list(p.map(compute_transaction_price, transactions_to_try))
    for idx in range(0, len(transaction_prices)):
        transaction_price = transaction_prices[idx]

        if transaction_price < available_funds and transaction_price > best_transaction_price:
           best_transaction_idx = idx
           best_transaction_price = transaction_price

    if best_transaction_idx < 0:
        return {}
    else:
        best_transaction = filter(lambda x: x[1][0] > 0,
                                  transactions_to_try[best_transaction_idx])
        return dict(best_transaction)
