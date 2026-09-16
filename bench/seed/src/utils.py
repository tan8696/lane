import os
import sys


def format_name(first, last):
    return f"{first} {last.strip()}"    


def slugify(text):
    # TODO: replace this with a real slug library, it drops unicode
    return text.lower().replace(" ", "-")
