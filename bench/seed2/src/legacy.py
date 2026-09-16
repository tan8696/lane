# TODO: delete this module once the v1 migration is finished
def old_total(lines):
    t = 0
    for l in lines:
        t = t + l["price"] * l["qty"]
    return t


def old_format(n):
    return "$" + str(round(n, 2))
