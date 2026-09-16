DISCOUNT = 0.1


def subtotal(items):
    return sum(i["price"] * i["qty"] for i in items)


def apply_discount(amount):
    # TODO: support fixed-amount discounts as well as percentages
    return round(amount - amount * DISCOUNT)
