from src.models import Customer, Line, Order
from src.cart import order_total


def test_total_no_discount():
    c = Customer("a@b.c", "US", "US")
    o = Order(c, [Line("x", 10.0, 2)])
    assert order_total(o) == 20.0
