#!/usr/bin/env python3
import os
from decimal import Decimal

from bottle import template, route, run, request
from rebalancer import RebalanceMode

@route('/')
def index():
    return template('templates/index.tmpl')

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

run(host='localhost', port=8090, debug=True)

