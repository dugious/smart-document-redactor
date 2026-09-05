import re

# Conservative ASCII mailbox detector, not an RFC-complete email parser.
EMAIL = re.compile(r"(?<![\w.!#$%&'*+/=?^`{|}~@-])[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?![\w@-])")


def detect_email(text: str):
    for match in EMAIL.finditer(text):
        value = match.group()
        local, domain = value.rsplit('@', 1)
        labels = domain.split('.')
        if (len(value) <= 254 and len(local) <= 64
                and not local.startswith('.') and not local.endswith('.')
                and '..' not in local
                and all(len(x) <= 63 and not x.startswith('-') and not x.endswith('-') for x in labels)
                and len(labels[-1]) >= 2 and labels[-1].isalpha()):
            yield match.start(), match.end(), value
