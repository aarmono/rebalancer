#!/usr/bin/env python3
import os
from decimal import Decimal
from collections import defaultdict
import argparse

from bottle import template, route, run, request, static_file
from rebalancer import RebalanceMode, Database, AssetAffinity, Session, AssetTaxGroup

QUOTE_KEY = None

@route('/')
def index():
    return template('www/templates/index.tmpl')

@route('/js/<filename:path>')
def send_static(filename):
    return static_file(filename, root='www/js')

@route('/get_token')
def get_token():
    return os.urandom(16).hex()

@route('/rebalance', method='POST')
def rebalance():
    token                  = request.forms.get('user_token')
    upload                 = request.files.get('upload')
    rebalance_mode_str     = request.forms.get('rebalance_mode')
    show_dollar_values_str = request.forms.get('show_dollar_values')
    fractional_shares_str  = request.forms.get('trade_fractional_shares')

    if upload is None:
        return "Must provide a portfolio csv file"

    name, ext = os.path.splitext(upload.filename)
    if ext not in ('.csv'):
        return 'File extension not allowed.'

    taxable_credit = None
    try:
        taxable_credit = Decimal(request.forms.get('taxable_credit')).copy_abs()
    except Exception:
        pass

    tax_deferred_credit = None
    try:
        tax_deferred_credit = Decimal(request.forms.get('tax_deferred_credit')).copy_abs()
    except Exception:
        pass

    rebalance_dict = dict(filter(lambda x: x[0][0] != '_',
                                 RebalanceMode.__dict__.items()))
    rebalance_mode = rebalance_dict.get(rebalance_mode_str, RebalanceMode.SELL_ALL)

    show_dollar_values = show_dollar_values_str == "true"
    fractional_shares = fractional_shares_str == "true"

    with Database() as database:
        salt = database.get_user_salt(token)
        if salt is None:
            database.add_user(token)
            database.commit()

            session = Session(token, database, upload.file)
            return template('www/templates/config.tmpl',
                            user_token = token,
                            session = session,
                            database = database)

        else:
            session = Session(token,
                              database,
                              upload.file,
                              taxable_credit,
                              tax_deferred_credit,
                              QUOTE_KEY,
                              fractional_shares)
            return template('www/templates/rebalance.tmpl',
                            user_token = token,
                            session = session,
                            show_dollar_values = show_dollar_values,
                            rebalance_mode = rebalance_mode)

@route('/configure', method='POST')
def configure_show():
    user_token = request.forms.get('user_token')
    upload     = request.files.get('upload')

    if upload is None:
        return "Must provide a portfolio csv file"

    name, ext = os.path.splitext(upload.filename)
    if ext not in ('.csv'):
        return 'File extension not allowed.'

    with Database() as database:
        salt = database.get_user_salt(user_token)
        if salt is None:
            database.add_user(user_token)
            database.commit()

        session = Session(user_token, database, upload.file)

        return template('www/templates/config.tmpl',
                        user_token = user_token,
                        session = session,
                        database = database)

@route('/configure/update', method='POST')
def configure_update():
    user_token = request.forms.get('user_token')

    affinities = []
    account_info = defaultdict(dict)
    asset_set = set()
    asset_target_values = {}
    asset_target_types = {}
    asset_sales_mask = set()
    asset_target_delete = set()

    def split_key(key):
        val = key.split('/')
        if len(val) == 2:
            return tuple(val)
        else:
            return (key, None)

    with Database() as database:
        asset_ids = dict(database.get_asset_abbreviations())

        asset_target_delete.update(set(request.forms.getall("delete_allocation")))

        for (key, value) in request.forms.items():
            try:
                (section, subelement) = split_key(key)
                if section == "accounts":
                    (account, account_key) = tuple(subelement.split('|'))
                    account_info[account][account_key] = value
                elif section == "affinity":
                    (tax_group, asset) = tuple(subelement.split('|'))
                    if value != "DISABLE" and asset not in asset_target_delete:
                        val = AssetAffinity(asset,
                                            tax_group,
                                            int(value))
                        affinities.append(val)
                elif section == "mask":
                    (tax_group, asset) = tuple(subelement.split('|'))
                    if asset not in asset_target_delete:
                        asset_sales_mask.add(AssetTaxGroup(asset, tax_group))
                elif section == "allocation":
                    if subelement not in asset_target_delete:
                        asset_set.add(subelement)

                        asset_target_values[subelement] = Decimal(value)
                elif section == "allocation_type":
                    if subelement not in asset_target_delete:
                        asset_set.add(subelement)

                        asset_target_types[subelement] = value
                elif section == "new_allocation":
                    if len(value) > 0:
                        asset_set.add(value)
                        asset_target_types[value] = 'Percent'
                        asset_target_values[value] = "0"
            except Exception as ex:
                print(ex)
                pass

        database.set_asset_affinities(user_token, affinities, asset_sales_mask)

        for account in account_info.keys():
            account_map = account_info[account]

            tax_group = account_map.get('tax_group')
            description = account_map.get('description')
            
            if tax_group is None or tax_group == "IGNORE":
                database.delete_account(user_token, account)
            else:
                database.add_account(user_token,
                                     account,
                                     description,
                                     tax_group)

        asset_targets = []
        for asset in asset_set:
            target_type = asset_target_types[asset]
            target = asset_target_values[asset]
            if target_type == "Percent" or target_type == "Percent Remainder":
                target = int(target * 10)
            elif target_type == "Dollars":
                target = int(target)
            else:
                raise KeyError("Invalid TargetType: %s" % (target_type))

            asset_targets.append((asset, target, target_type))

        percent_targets = list(filter(lambda x: x[2] == 'Percent', asset_targets))
        sum_percents = sum(map(lambda x: x[1], percent_targets))

        remainder_targets = list(filter(lambda x: x[2] == 'Percent Remainder', asset_targets))
        sum_remainders = sum(map(lambda x: x[1], remainder_targets))

        if len(percent_targets) > 0 and len(remainder_targets) == 0 and sum_percents != 1000:
            pass
        elif len(remainder_targets) > 0 and sum_remainders != 1000:
            pass
        else:
            database.set_asset_targets(user_token, asset_targets)

        database.commit()

        assets = sorted(asset_set, key=lambda x: asset_ids[x])
        session = Session(user_token, database)

        return template('www/templates/config_simple.tmpl',
                        user_token = user_token,
                        accounts = list(account_info.keys()),
                        account_target = session.get_account_target(),
                        assets = assets,
                        asset_sales_mask = asset_sales_mask,
                        database = database)

@route('/security_configure')
def security_configure():
    with Database() as database:
        return template('www/templates/security_config.tmpl', database = database)

@route('/security_configure/update', method='POST')
def security_configure_update():
    with Database() as database:
        if "symbol/symbol" in request.forms:
            symbol = request.forms.get("symbol/symbol")
            asset = request.forms.get("symbol/asset_class")
            default = request.forms.get("symbol/default", "false") == "true"

            if symbol is not None and len(symbol) > 0:
                database.add_symbol(symbol, asset, default)

            for symbol in request.forms.getall('symbol/delete'):
                database.delete_symbol(symbol)

        elif "asset/asset" in request.forms:
            asset = request.forms.get("asset/asset")
            asset_group = request.forms.get("asset/asset_group")

            if asset is not None and len(asset) > 0:
                database.add_asset(asset, asset_group)

            for asset in request.forms.getall('asset/delete'):
                database.delete_asset(asset)

            for symbol in request.forms.getall('asset/default'):
                database.set_default_security(symbol)

        elif "asset_group/asset_group" in request.forms:
            asset_group = request.forms.get("asset_group/asset_group")

            if asset_group is not None and len(asset_group) > 0:
                database.add_asset_group(asset_group)

            for asset_group in request.forms.getall('asset_group/delete'):
                database.delete_asset_group(asset_group)

        database.commit()

        return template('www/templates/security_config.tmpl', database = database)


def main():
    parser = argparse.ArgumentParser(description='Rebalance server')
    parser.add_argument('--bind', dest='host', type=str, default='127.0.0.1',
                        help='bind to specified ip address')
    parser.add_argument('--port', dest='port', type=int, default=8090,
                        help='bind to specified port')
    parser.add_argument('--debug', dest='debug', action='store_true',
                        help='Enable debug mode in HTTP server')
    parser.add_argument('--quote-key', dest='quote_key', type=str, default=None,
                        help='Alphavantage API key for real-time quote data')

    args = parser.parse_args()

    global QUOTE_KEY
    QUOTE_KEY = args.quote_key

    run(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()
