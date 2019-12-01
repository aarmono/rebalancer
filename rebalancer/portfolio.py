from decimal import Decimal
from functools import reduce, partial
from collections import defaultdict
from math import ceil, floor

from .utils import round_cents, to_dollars, is_mutual_fund
from .balance import compute_asset_differences, compute_minimal_remainder_purchase

class Transaction:
    SELL = "Sell"
    BUY = "Buy"

    def __init__(self, t_type, symbol, amount, cost_per_share = None, shares = None):
        self.__t_type = t_type
        self.__symbol = symbol
        self.__shares = shares
        self.__cost_per_share = cost_per_share
        self.__amount = amount

    def transaction_type(self):
        return self.__t_type

    def amount(self):
        return self.__amount

    def symbol(self):
        return self.__symbol

    def cost_per_share(self):
        return self.__cost_per_share

    def shares(self):
        return self.__shares

class Account:
    def __init__(self, security_db):
        self.__positions = {}
        self.__assets_to_symbols = {}
        self.__security_db = security_db

    def add_position(self, symbol, value):
        if symbol in self.__positions:
            raise KeyError("%s already exists in this Account" % (symbol))
        else:
            asset = self.__security_db.get_asset_class(symbol)
            if asset in self.__assets_to_symbols:
                raise KeyError("%s asset already exists in this Account" % (asset))
            else:
                self.__assets_to_symbols[asset] = symbol
                self.__positions[symbol] = value


    def __getitem__(self, asset):
        return self.__positions[self.__assets_to_symbols[asset]]

    def get_position_transactions(self,
                                  sell_asset_transactions,
                                  buy_asset_transactions):
        ret = []

        available_funds = Decimal(0.0)
        for (asset, value) in sell_asset_transactions.items():
            symbol = self.__assets_to_symbols[asset]
            position = self.__positions[symbol]

            shares = None
            cost_per_share = None
            if not self.__security_db.supports_fractional_shares(symbol):
                cost_per_share = self.__security_db.get_current_price(symbol)
                shares = Decimal(min(ceil(value / cost_per_share),
                                     floor(position / cost_per_share)))
                value = shares * cost_per_share

            available_funds += value

            t = Transaction(Transaction.SELL, symbol, value, cost_per_share, shares)
            ret.append(t)

        unoptomized_sale_funds = Decimal(0.0)
        has_mutual_funds = False
        buy_symbols = {}
        for (asset, value) in buy_asset_transactions.items():
            symbol = None
            cost_per_share = None
            if asset not in self.__assets_to_symbols:
                symbol = self.__security_db.get_reference_security(asset)
            else:
                symbol = self.__assets_to_symbols[asset]

            cost_per_share = self.__security_db.get_current_price(symbol)
            shares = None
            if not self.__security_db.supports_fractional_shares(symbol):
                shares = int(floor(value / cost_per_share))
            else:
                if self.__security_db.get_asset_class(symbol) != "Cash":
                    has_mutual_funds = True
                shares = value / cost_per_share

            buy_symbols[symbol] = (shares, cost_per_share)
            unoptomized_sale_funds += shares * cost_per_share

        if not has_mutual_funds:
            buy_symbols = compute_minimal_remainder_purchase(buy_symbols,
                                                             available_funds,
                                                             self.__positions)
        else:
            # Evenly split the remaining funds between all mutual funds in
            # the account. Since the remaining amount should be small (price
            # of one share) this should not affect the portfolio composition
            def filt(s): return self.__security_db.supports_fractional_shares(s) and \
                                self.__security_db.get_asset_class(s) != "Cash"

            mutual_fund_symbols = list(filter(filt, buy_symbols.keys()))
            num_mutual_funds = len(mutual_fund_symbols)
            total_remaining_funds = available_funds - unoptomized_sale_funds
            funds_per_mutual_fund = round_cents(total_remaining_funds / num_mutual_funds)
            for symbol in mutual_fund_symbols:
                (shares, cost_per_share) = buy_symbols[symbol]
                shares += (funds_per_mutual_fund / cost_per_share)
                buy_symbols[symbol] = (shares, cost_per_share)
                total_remaining_funds -= funds_per_mutual_fund
                funds_per_mutual_fund = min(funds_per_mutual_fund, total_remaining_funds)


        for (symbol, (shares, cost_per_share)) in buy_symbols.items():
            value = shares * cost_per_share
            if isinstance(shares, Decimal):
                # This field is just for presentation purposes and isn't used
                # for any calculations, so rounding is safe
                shares = shares.quantize(Decimal('1.00'))

            t = Transaction(Transaction.BUY, symbol, value, cost_per_share, shares)
            ret.append(t)

        if len(buy_symbols) == 0:
            ret.clear()

        return ret

    def get(self, asset, default=None):
        symbol = self.__assets_to_symbols.get(asset)
        return self.__positions[symbol] if symbol is not None else default

    def current_value(self):
        return sum(self.__positions.values())

    def items(self):
        ret = []
        for (symbol, value) in self.__positions.items():
            ret.append((self.__security_db.get_asset_class(symbol), value))

        return ret

    def keys(self):
        return list(self.__assets_to_symbols.keys())

    def copy(self, transactions):
        account_copy = Account(self.__security_db)

        sell_amount = Decimal(0.0)
        buy_amount = Decimal(0.0)

        tmp_positions = self.__positions.copy()
        for transaction in transactions:
            symbol = transaction.symbol()
            amount = transaction.amount()
            if transaction.transaction_type() == Transaction.SELL:
                tmp_positions[symbol] -= amount
                sell_amount += amount

            elif transaction.transaction_type() == Transaction.BUY:
                if symbol not in tmp_positions:
                    tmp_positions[symbol] = amount
                else:
                    tmp_positions[symbol] += amount

                buy_amount += amount

        if "Cash" not in self.__assets_to_symbols:
            tmp_positions["CORE"] = Decimal(0.0)
        else:
            sweep = self.__assets_to_symbols["Cash"]
            tmp_positions[sweep] += (sell_amount - buy_amount)

        for (symbol, position) in tmp_positions.items():
            account_copy.add_position(symbol, position)

        return account_copy

class AccountGroupBase:
    def __init__(self, accounts):
        self._accounts = accounts

    def current_value(self):
        return reduce(lambda x, y: x + y.current_value(),
                      self._accounts.values(),
                      Decimal(0.0))

    def __getitem__(self, asset):
        ret = self.get(asset)

        if ret is None:
            raise KeyError
        else:
            return ret

    def get(self, asset, default=None):
        ret = None
        for account in self._accounts.values():
            cur = account.get(asset)
            if cur is not None:
                ret = cur if ret is None else ret + cur

        return ret if ret is not None else default

    def items(self):
        ret = defaultdict(Decimal)
        for account in self._accounts.values():
            for (asset, value) in account.items():
                ret[asset] += value

        return list(ret.items())

    def keys(self):
        ret = set()
        for account in self._accounts.values():
            ret.update(account.keys())

        return list(ret)

class AccountGroup(AccountGroupBase):
    def __init__(self, security_db):
        self.__security_db = security_db
        AccountGroupBase.__init__(self, defaultdict(partial(Account, security_db)))

    def add_position(self, account, symbol, value):
        self._accounts[account].add_position(symbol, value)

    def get_transactions_to_match_target(self, target_assets):
        group_asset_differences = compute_asset_differences(self, target_assets)
        group_up_assets = list(filter(lambda key: group_asset_differences[key] > Decimal(0.0),
                                      group_asset_differences.keys()))
        group_down_assets = list(filter(lambda key: group_asset_differences[key] < Decimal(0.0),
                                        group_asset_differences.keys()))

        sell_transactions = defaultdict(dict)
        buy_transactions = defaultdict(dict)

        cash_available = defaultdict(Decimal)

        for up_asset in group_up_assets:
            for (name, account) in self._accounts.items():
                available = account.get(up_asset, Decimal(0.0))
                difference = group_asset_differences[up_asset]
                if difference > Decimal(0.0) and available > Decimal(0.0):

                    value = min(available, difference)
                    sell_transactions[name][up_asset] = value
                    group_asset_differences[up_asset] -= value
                    cash_available[name] += value

        for down_asset in group_down_assets:
            for (name, account) in self._accounts.items():
                available = cash_available[name]
                difference = group_asset_differences[down_asset]
                if difference < Decimal(0.0) and available > Decimal(0.0):

                    value = min(available, -difference)
                    buy_transactions[name][down_asset] = value
                    group_asset_differences[down_asset] += value
                    cash_available[name] -= value

        ret = {}
        for (name, account) in self._accounts.items():
            sell = sell_transactions.get(name, {})
            buy = buy_transactions.get(name, {})

            ret[name] = account.get_position_transactions(sell, buy)

        return ret

    def copy(self, transaction_group):
        account_group_copy = AccountGroup(self.__security_db)

        for (account, transactions) in transaction_group.items():
            account_group_copy._accounts[account] = self._accounts[account].copy(transactions)

        return account_group_copy

class Portfolio(AccountGroupBase):
    def __init__(self, security_db, tax_status):
        AccountGroupBase.__init__(self, defaultdict(partial(AccountGroup, security_db)))
        self.__security_db = security_db
        self.TaxStatus = tax_status

    def add_position(self, account, tax_status, symbol, position):
        self._accounts[tax_status].add_position(account, symbol, position)

    def assets_by_tax_status(self):
        return self._accounts.copy()

    def get_transactions_to_match_target(self, target_tax_groups):
        ret = {}
        for (tax_group, target_assets) in target_tax_groups.items():
            account_group = self._accounts[tax_group]
            ret[tax_group] = account_group.get_transactions_to_match_target(target_assets)

        return ret

    def copy_with_transactions_applied(self, transaction_groups):
        portfolio_copy = Portfolio(self.__security_db, self.TaxStatus)

        for (tax_status, transaction_group) in transaction_groups.items():
            portfolio_copy._accounts[tax_status] = self._accounts[tax_status].copy(transaction_group)

        return portfolio_copy
