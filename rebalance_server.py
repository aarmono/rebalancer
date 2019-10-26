#!/usr/bin/env python3
import os
from decimal import Decimal
from collections import defaultdict

from bottle import template, route, run, request
from rebalancer import RebalanceMode, Database, AssetAffinity

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

run(host='localhost', port=8090, debug=True)

