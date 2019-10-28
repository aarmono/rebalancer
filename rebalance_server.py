#!/usr/bin/env python3
import os
from decimal import Decimal
from collections import defaultdict
import argparse

from bottle import template, route, run, request
from rebalancer import RebalanceMode, Database, AssetAffinity, Session, hash_user_token, hash_user_token_with_salt

QUOTE_KEY = None

@route('/')
def index():
    return template('templates/index.tmpl')

@route('/get_token')
def get_token():
    return os.urandom(16).hex()

@route('/rebalance', method='POST')
def rebalance():
    token              = request.forms.get('user_token')
    upload             = request.files.get('upload')
    rebalance_mode_str = request.forms.get('rebalance_mode')

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

    rebalance_mode = RebalanceMode.FULL
    if rebalance_mode_str == "FULL":
        rebalance_mode = RebalanceMode.FULL
    elif rebalance_mode_str == "NO_SELL_TAXABLE":
        rebalance_mode = RebalanceMode.NO_SELL_TAXABLE
    elif rebalance_mode_str == "NO_SELL":
        rebalance_mode = RebalanceMode.NO_SELL

    hashed_token_system_salt = hash_user_token(token)
    with Database() as database:
        salt = database.get_user_salt(user_hash = hashed_token_system_salt)
        if salt is None:
            database.add_user(user_hash = hashed_token_system_salt)
            database.commit()

            session = Session(token, database, upload.file)
            return template('templates/config.tmpl',
                            user_token = token,
                            session = session,
                            database = database)

        else:
            session = Session(token,
                              database,
                              upload.file,
                              taxable_credit,
                              tax_deferred_credit,
                              QUOTE_KEY)
            return template('templates/rebalance.tmpl',
                            user_token = token,
                            session = session,
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

    hashed_token_system_salt = hash_user_token(user_token)

    with Database() as database:
        salt = database.get_user_salt(user_hash = hashed_token_system_salt)
        if salt is None:
            database.add_user(user_hash = hashed_token_system_salt)
            database.commit()

        session = Session(user_token, database, upload.file)

        return template('templates/config.tmpl',
                        user_token = user_token,
                        session = session,
                        database = database)

@route('/configure/update', method='POST')
def configure_update():
    user_token = request.forms.get('user_token')

    affinities = []
    account_info = defaultdict(dict)
    asset_set = set()
    asset_deci_perentages = {}

    with Database() as database:
        salt = database.get_user_salt(user_token = user_token)
        hashed_token_user_salt = hash_user_token_with_salt(user_token, salt = salt)

        asset_ids = dict(database.get_asset_abbreviations())

        for (key, value) in request.forms.items():
            try:
                (section, subelement) = tuple(key.split('/'))
                if section == "accounts":
                    (account, account_key) = tuple(subelement.split('|'))
                    account_info[account][account_key] = value
                elif section == "affinity":
                    (tax_group, asset) = tuple(subelement.split('|'))
                    if value != "DISABLE":
                        val = AssetAffinity(asset,
                                            tax_group,
                                            int(value))
                        affinities.append(val)
                elif section == "allocation":
                    asset_set.add(subelement)

                    deci_percent = int(Decimal(value) * 10)
                    asset_deci_perentages[subelement] = deci_percent
            except Exception as ex:
                print(ex)
                pass

        database.set_asset_affinities(user_token, affinities)

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

        database.set_asset_targets(hashed_token_user_salt,
                                   asset_deci_perentages.items())

        database.commit()

        assets = sorted(asset_set, key=lambda x: asset_ids[x])
        session = Session(user_token, database)

        return template('templates/config_simple.tmpl',
                        user_token = user_token,
                        accounts = list(account_info.keys()),
                        account_target = session.get_account_target(),
                        assets = assets,
                        database = database)

@route('/security_configure')
def security_configure():
    with Database() as database:
        return template('templates/security_config.tmpl', database = database)

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

        return template('templates/security_config.tmpl', database = database)


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
