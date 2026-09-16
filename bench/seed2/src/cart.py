from src.pricing import subtotal, discount_for, tax_for


def order_total(order):
    sub = subtotal(order)
    disc = discount_for(sub)
    tax = tax_for(order)
    return round(sub - disc + tax, 2)
