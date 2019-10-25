from decimal import Decimal

def to_dollars(value):
    value = round_cents(value)
    return "$%s" % ('{:,}'.format(value)) if value >= Decimal(0.0) else '-$%s' % ('{:,}'.format(abs(value)))

def round_cents(value):
    return value.quantize(Decimal('1.00'))

def is_mutual_fund(symbol):
    # Mutual fund symbols are 5 characters long
    # Remove any asterisks which denote a sweep account
    return len(symbol.replace('*', '')) == 5

def is_sweep(symbol):
    return '*' in symbol

def compute_percent_difference(current_value, target_value):
    if target_value != Decimal(0.0):
        difference = (current_value - target_value) / target_value
        return (difference * 100).quantize(Decimal('1.00'))
    elif current_value < target_value:
        return Decimal('-inf')
    else:
        return Decimal('inf')

def to_enum_name(text):
    return text.replace(' ', '_').replace('-', '_').upper()

def get_token_from_file():
    user_token = None
    try:
        with open(".token", "x") as f:
            user_token = uuid4().hex
            f.write(user_token)
    except Exception:
        with open(".token", "r") as f:
            user_token = f.read()

    return user_token