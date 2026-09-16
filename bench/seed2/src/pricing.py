TAX_RATES = {"DE": 0.19, "FR": 0.20, "US": 0.0}
DISCOUNT_TIERS = ((500.0, 0.10), (100.0, 0.05))


def subtotal(order):
    return round(sum(l.price * l.qty for l in order.lines), 2)


def discount_for(amount):
    for threshold, rate in DISCOUNT_TIERS:
        if amount >= threshold:
            return round(amount * rate, 2)
    return 0.0


def tax_for(order):
    rate = TAX_RATES.get(order.customer.shipping_country, 0.0)
    return round(subtotal(order) * rate, 2)
