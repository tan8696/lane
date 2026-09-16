from dataclasses import dataclass, field


@dataclass
class Customer:
    email: str
    billing_country: str
    shipping_country: str


@dataclass
class Line:
    sku: str
    price: float
    qty: int


@dataclass
class Order:
    customer: Customer
    lines: list = field(default_factory=list)
