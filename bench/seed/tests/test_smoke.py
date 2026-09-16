from src.cart import subtotal


def test_subtotal():
    assert subtotal([{"price": 2.0, "qty": 3}]) == 6.0
