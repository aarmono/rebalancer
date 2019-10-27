#!/usr/bin/env python3
import os
from decimal import Decimal
from collections import defaultdict

from bottle import template, route, run, request
from rebalancer import RebalanceMode, Database, AssetAffinity, Session, AccountTarget, SecurityDatabase, hash_user_token, hash_user_token_with_salt

@route('/')
def index():
    return template('templates/index.tmpl')

@route('/get_token')
def get_token():
    return os.urandom(16).hex()

@route('/result', method='POST')
def result():
    token              = request.forms.get('user_token')
    upload             = request.files.get('upload')
    rebalance_mode_str = request.forms.get('rebalance_mode')
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

    return template('templates/result.tmpl',
                    user_token=token,
                    portfolio_file=upload.file,
                    rebalance_mode=rebalance_mode,
                    taxable_credit=taxable_credit,
                    tax_deferred_credit=tax_deferred_credit)

@route('/asset_affinity', method='POST')
def asset_affinity_show():
    token = request.forms.get('user_token')

    return template('templates/asset_config.tmpl',
                    user_token=token)

@route('/asset_affinity/update', method='POST')
def asset_affinity_update():
    token = request.forms.get('user_token')

    with Database() as db:
        asset_ids = dict(db.get_asset_abbreviations())
        tax_group_ids = dict(db.get_tax_groups())

        affinities = []
        for (key, priority) in request.forms.items():
            try:
                (tax_group, asset) = tuple(key.split('|'))
                if priority != "DISABLE":
                    val = AssetAffinity(asset_ids[asset],
                                        tax_group_ids[tax_group],
                                        int(priority))
                    affinities.append(val)
            except Exception as ex:
                pass

        db.set_asset_affinities(token, affinities)
        db.commit()

    return template('templates/asset_config.tmpl',
                    user_token=token)

@route('/account_config', method='POST')
def account_config_show():
    token = request.forms.get('user_token')
    upload = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    if ext not in ('.csv'):
        return 'File extension not allowed.'

    return template('templates/account_config.tmpl',
                    user_token=token,
                    portfolio_file=upload.file)

@route('/account_config/update', method='POST')
def account_config_update():
    token = request.forms.get('user_token')

    account_info = defaultdict(dict)
    with Database() as db:
        tax_group_ids = dict(db.get_tax_groups())

        affinities = []
        for (key, value) in request.forms.items():
            try:
                (account, account_key) = tuple(key.split('|'))
                account_info[account][account_key] = value
            except Exception as ex:
                pass

        for account in account_info.keys():
            account_map = account_info[account]

            tax_group = account_map.get('tax_group')
            description = account_map.get('description')
            
            if tax_group is None or tax_group not in tax_group_ids:
                db.delete_account(token, account)
            else:
                tax_group_id = tax_group_ids[tax_group]
                db.add_account(token,
                               account,
                               description,
                               tax_group_id)

        db.commit()

    return template('templates/account_config_display.tmpl',
                    user_token=token,
                    accounts=list(account_info.keys()))

@route('/target_config', method='POST')
def target_config():
    token = request.forms.get('user_token')
    upload = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    if ext not in ('.csv'):
        return 'File extension not allowed.'

    session = Session(token, upload.file)
    portfolio = session.get_portfolio()
    account_target = session.get_account_target()

    assets = None
    with Database() as db:
        asset_ids = dict(db.get_asset_abbreviations())
        assets = sorted(portfolio.keys(), key=lambda x: asset_ids[x])

    return template('templates/target_asset_config.tmpl',
                    user_token=token,
                    assets=assets,
                    account_target=account_target)

@route('/target_config/update', method='POST')
def target_config():
    token = request.forms.get('user_token')
    user_hash = hash_user_token(token)

    with Database() as db:
        salt = db.get_user_salt(user_hash = user_hash)
        if salt is None:
            db.add_user(user_hash = user_hash)
            salt = db.get_user_salt()

        salted_user_token = hash_user_token_with_salt(token, salt = salt)

        asset_ids = dict(db.get_asset_abbreviations())
        asset_deci_perentages = {}

        asset_set = set()
        for (key, value) in request.forms.items():
            try:
                (asset_str, asset) = tuple(key.split('|'))
                if asset_str == "allocation":
                    asset_set.add(asset)

                    deci_percent = int(Decimal(value) * 10)
                    asset_deci_perentages[asset_ids[asset]] = deci_percent
            except Exception as ex:
                pass

        db.set_asset_targets(salted_user_token, asset_deci_perentages.items())
        db.commit()

        securities = SecurityDatabase(None, db)
        account_target = AccountTarget(token, securities, db)
        assets = sorted(asset_set, key=lambda x: asset_ids[x])

        return template('templates/target_asset_config.tmpl',
                        user_token=token,
                        assets=assets,
                        account_target=account_target)

run(host='localhost', port=8090, debug=True)

