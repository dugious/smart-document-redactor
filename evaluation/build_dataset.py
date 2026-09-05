"""Author gold with inline tags, never by running a detector. Synthetic only."""
import json
from pathlib import Path
import re

DEV = [
    'Please contact <PERSON>Clara Whitmore</PERSON> at <EMAIL>clara@example.org</EMAIL>.',
    'Help desk: <PHONE>202-555-0121</PHONE>. Test card <CREDIT_CARD>5555 5555 5555 4444</CREDIT_CARD>.',
    'Delivery for <PERSON>Owen Fletcher</PERSON>: <ADDRESS>18 Maple Road</ADDRESS>.',
    'Public figures: revenue 123.45, year 2026, city London.',
    'Ask <PERSON>Nora Bell</PERSON> or <PERSON>Nora Bell</PERSON> for the report.',
    'International contact <PHONE>+44 20 7946 0123</PHONE>; office <ADDRESS>7 High Street, London SW1A 1AA</ADDRESS>.',
]
TEST = [
    'Employee <PERSON>Alice Morgan</PERSON> submitted her report. Reply to <EMAIL>alice.morgan@example.com</EMAIL>.',
    'The signed agreement lists <PERSON>Daniel Brooks</PERSON> as the reviewer.',
    'Interview participants were <PERSON>Sofia Bennett</PERSON> and <PERSON>Marcus Reed</PERSON>.',
    'Emergency contact: <PERSON>Emily Carter</PERSON>, telephone <PHONE>+1 202-555-0100</PHONE>.',
    'Billing telephone <PHONE>(415) 555-0114</PHONE> and backup <PHONE>212.555.0198 ext. 21</PHONE>.',
    'Payment sandbox values: <CREDIT_CARD>4111 1111 1111 1111</CREDIT_CARD> and <CREDIT_CARD>378282246310005</CREDIT_CARD>.',
    'Send the parcel to <ADDRESS>123 Example Street, Apt 4</ADDRESS>.',
    'The warehouse entrance is at <ADDRESS>42 Cedar Avenue</ADDRESS>.',
    'Forward to <EMAIL>team+review@example.net</EMAIL>; CC <EMAIL>team+review@example.net</EMAIL>.',
    'A message from <PERSON>Liam Hayes</PERSON>:\nPlease call <PHONE>303-555-0173</PHONE> tomorrow.',
    'Recipient: <PERSON>Grace Palmer</PERSON>\nAddress: <ADDRESS>89 Willow Lane</ADDRESS>\nEmail: <EMAIL>grace@example.org</EMAIL>',
    'The public report mentions Paris, Berlin, 2025-04-12 and a balance of 987.65.',
    'Order IDs: 123456, 1234567890123456789012345. Version 3.13.14.',
    'This paragraph has no personal contact details or named individuals.',
    'Staff member <PERSON>Henry Sullivan</PERSON> approved the request from <PERSON>Chloe Turner</PERSON>.',
    'Call <PHONE>+44 20 7946 0958</PHONE> for the international office.',
    'Mobile contact without separators: <PHONE>2025550182</PHONE>.',
    'Postal delivery: <ADDRESS>56 Oak Street, Boston, MA 02110</ADDRESS>.',
    'Lowercase address entered by user: <ADDRESS>81 pine road</ADDRESS>.',
    'Mailbox routing: <ADDRESS>PO Box 123, Seattle, WA 98101</ADDRESS>.',
    'Customer <PERSON>Isabella Quinn</PERSON> uses <EMAIL>isabella@example.com</EMAIL>. Test card <CREDIT_CARD>6011-1111-1111-1117</CREDIT_CARD>.',
    'Repeat participant <PERSON>Noah Ellis</PERSON>, then <PERSON>Noah Ellis</PERSON>.',
    'Please notify <PERSON>Maya Collins</PERSON> about the change to <ADDRESS>67 Birch Drive, Unit 8</ADDRESS>.',
    'Accounting sample: <CREDIT_CARD>5555555555554444</CREDIT_CARD>. Public subtotal 420.00.',
]
PATTERN = re.compile(r'<(PERSON|EMAIL|PHONE|CREDIT_CARD|ADDRESS)>(.*?)</\1>', re.DOTALL)


def materialize(tagged: str, doc_id: str):
    text, spans, cursor = '', [], 0
    for match in PATTERN.finditer(tagged):
        text += tagged[cursor:match.start()]
        start = len(text)
        text += match.group(2)
        spans.append({'type': match.group(1), 'start': start, 'end': len(text)})
        cursor = match.end()
    text += tagged[cursor:]
    if '<' in text or '>' in text:
        raise ValueError('Unparsed gold tag')
    return {'id': doc_id, 'text': text, 'entities': spans}


if __name__ == '__main__':
    folder = Path(__file__).resolve().parent
    for split, rows in [('dev', DEV), ('test', TEST)]:
        documents = [materialize(row, f'{split}-{i:03}') for i, row in enumerate(rows, 1)]
        (folder / f'{split}.jsonl').write_text(''.join(json.dumps(d, ensure_ascii=False)+'\n' for d in documents), encoding='utf-8')
    print('Generated frozen synthetic gold: 6 dev / 24 test documents.')
