import os
import sys
import json


def format_name(first, last):
    return f"{first} {last}".strip()    


def slugify(text):
    # TODO: replace with a real slug library, this drops unicode
    return text.lower().replace(" ", '-')
