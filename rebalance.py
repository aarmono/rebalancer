#!/usr/bin/env python3

from decimal import Decimal
from math import ceil, floor
from itertools import chain
from functools import partial

from rebalancer import *

VERBOSE = False

SWEEP = 'FZFXX'

def print_balances(account_target, portfolio):
    target_values = account_target.get_target_asset_values(portfolio)
    for (symbol, value) in portfolio.items():
        if symbol in target_values:
            target = target_values[symbol]
            difference = value - target
            print("%12s: %14s (target: %14s, difference: %14s)" % (symbol,
                                                                   to_dollars(value),
                                                                   to_dollars(target),
                                                                   to_dollars(difference)))
        else:
            print("%12s: %14s" % (symbol, to_dollars(value)))

    print("")
    print("Current value: %12s" % (to_dollars(portfolio.current_value())))

def print_composition(title, account_target, portfolio):
    print(title + ":")
    total_value = portfolio.current_value()
    target_values = account_target.get_target_asset_values(portfolio)
    target_percentages = account_target.get_target_asset_percentages()
    for (symbol, value) in portfolio.items():
        actual_percent = ((value / total_value) * 100).quantize(Decimal('1.0'))
        target_value = target_values[symbol]
        if symbol in target_values:
            difference = value - target_value

            target_percent = (target_percentages[symbol] * 100).quantize(Decimal('1.0'))
            point_difference = actual_percent - target_percent
            if target_values[symbol] > 0:
                percent_difference = compute_percent_difference(value,
                                                                target_value)
                print("%12s: %4s%% (target: %4s%%, difference: %5s%% (%7s%%))" % (symbol,
                                                                                  actual_percent,
                                                                                  target_percent,
                                                                                  point_difference,
                                                                                  percent_difference))
            else:
                print("%12s: %4s%% (target: %4s%%, difference: %5s%%           )" % (symbol,
                                                                                     actual_percent,
                                                                                     target_percent,
                                                                                     point_difference))
        else:
            print("%12s: %4s%%" % (symbol, acual_percent))

    if VERBOSE:
        print("")
        print_balances(account_target, portfolio)

    print("")
    group_target_values = account_target.get_target_asset_group_values(portfolio)
    group_actual_values = account_target.get_actual_asset_group_values(portfolio)
    group_percentages = account_target.get_target_asset_group_percentages()
    for (group, target_value) in group_target_values.items():
        actual_value = group_actual_values[group]
        group_percent = ((actual_value / total_value) * 100).quantize(Decimal('1.0'))
        group_target_percent = (group_percentages[group] * 100).quantize(Decimal('1.0'))


        print("%8s: %9s%% (target: %9s%%)" % (group, group_percent,
                                              group_target_percent))

    print("")

def print_transactions(transaction_groups):
    for account_group in transaction_groups.values():
        for (account, transactions) in filter(lambda x: len(x[1]) > 0,
                                              account_group.items()):
            print(account + ":")

            sell_transactions = list(filter(lambda x: x.transaction_type() == Transaction.SELL, transactions))
            buy_transactions = list(filter(lambda x: x.transaction_type() == Transaction.BUY, transactions))

            if len(sell_transactions) > 0:
                print("Sell the following shares:")
                sale_total = Decimal(0.0)
                for transaction in sell_transactions:
                    symbol = transaction.symbol()
                    shares = transaction.shares()
                    sell_price = transaction.cost_per_share()
                    sale_value = transaction.amount()
                    sale_total += transaction.amount()

                    if shares is not None and sell_price is not None:
                        print("%8s: %12s (%8s shares @ %7s/share)" % (symbol,
                                                                     to_dollars(sale_value),
                                                                     shares,
                                                                     to_dollars(sell_price)))
                    else:
                        print("%8s: %12s" % (symbol, to_dollars(sale_value)))

                print("")
                print("Sale Total: %12s" % (to_dollars(sale_total)))
                print("")

            if len(buy_transactions) > 0:
                print("Buy the following shares:")
                purchase_total = Decimal(0.0)
                for transaction in buy_transactions:
                    symbol = transaction.symbol()
                    shares = transaction.shares()
                    sell_price = transaction.cost_per_share()
                    sale_value = transaction.amount()
                    purchase_total += transaction.amount()

                    if shares is not None and sell_price is not None:
                        print("%8s: %12s (%8s shares @ %7s/share)" % (symbol,
                                                                     to_dollars(sale_value),
                                                                     shares,
                                                                     to_dollars(sell_price)))
                    else:
                        print("%8s: %12s" % (symbol, to_dollars(sale_value)))

                print("")
                print("Purchase Total: %12s" % (to_dollars(purchase_total)))
                print("")

def main():
    from optparse import OptionParser

    usage = "usage: %prog [options] /path/to/fidelity_portolio.csv"
    parser = OptionParser(usage=usage)
    parser.add_option("-n", "--no-sell",
                      action="store_true", dest="no_sell", default=False,
                      help="Attempt to rebalance without selling shares")
    parser.add_option("-c", "--credit",
                      action="store", dest="credit", default=None, type="float",
                      help="Amount of unsettled credit with which to trade")
    parser.add_option("-p", "--position",
                      action="append", dest="credits", default=[], type="string",
                      help="Additional value to add to a position in form <symbol>:<dollar amount>")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="Verbose output")

    (options, args) = parser.parse_args()
    rebalance_mode = RebalanceMode.NO_SELL if options.no_sell else RebalanceMode.SELL_ALL

    apikey = None
    try:
      with open('.quotekey', 'r') as f:
        apikey = f.read()
    except Exception:
      pass

    global VERBOSE
    VERBOSE = options.verbose

    credit = None
    if options.credit is not None:
        credit = round_cents(Decimal(options.credit))

    user_token = get_token_from_file()
    with Database() as database:
        session = Session(user_token, database, args[0], credit, None, apikey)

        portfolio = session.get_portfolio()
        rebalancer = session.get_rebalancer()
        account_target = session.get_account_target()

        targets_by_tax_group = rebalancer.compute_target_asset_values(portfolio,
                                                                      rebalance_mode)
        portfolio_transactions = portfolio.get_transactions_to_match_target(targets_by_tax_group)

        print_composition("Portfolio composition", account_target, portfolio)

        print_transactions(portfolio_transactions)

        new_portfolio = portfolio.copy_with_transactions_applied(portfolio_transactions)

        print_composition("New Portfolio composition", account_target, new_portfolio)

if __name__ == "__main__":
    import sys
    main()