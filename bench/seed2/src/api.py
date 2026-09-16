from src.cart import order_total
from src.db import get_user


def handle_checkout(order):
    # TODO: this function is doing too much, split it up
    user = get_user(order.customer.email)
    if user is None:
        return {"status": 404}
    return {"status": 200, "total": order_total(order)}
