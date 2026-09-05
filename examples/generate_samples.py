from pathlib import Path
import pymupdf
from smart_redactor.pipeline import process_pdf


def main():
    folder = Path(__file__).resolve().parent
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 60), 'SYNTHETIC DEMO - no real personal information')
        page.insert_text((50, 100), 'Contact: demo@example.com')
        page.insert_text((50, 140), 'Repeated: demo@example.com')
        page.insert_text((50, 180), 'Public amount: 123.45 - keep this text')
        source = doc.tobytes()
    (folder / 'synthetic-input.pdf').write_bytes(source)
    _, output = process_pdf(source)
    (folder / 'synthetic-redacted.pdf').write_bytes(output)
    print('Generated synthetic input and verified output in examples/.')


if __name__ == '__main__':
    main()
