import re
import unicodedata


def clean_name(name, source):
    if source == 'coolpc':
        # Keep the content (it may contain a model number), remove presentation braces.
        name = re.sub(r'[{}｛｝]', '', name)
    return re.sub(r'\s+', ' ', name).strip()


def normalized(name):
    return unicodedata.normalize('NFKC', name).upper()
