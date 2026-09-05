"""Explicit real-model smoke checks. No download; not a benchmark."""
import pymupdf
from smart_redactor.detection.ner import SpacyBackend, TransformersBackend
from smart_redactor.text import process_txt
from smart_redactor.pipeline import process_pdf


def main():
    sample = 'Barack Obama met Angela Merkel in London. Email: demo@example.com'
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 60), sample, fontsize=10)
        pdf = doc.tobytes()
    for factory in (SpacyBackend, TransformersBackend):
        backend = factory()
        analysis, output = process_txt(sample.encode(), backend=backend)
        assert any(e.type == 'PERSON' for e in analysis.entities)
        assert b'Barack Obama' not in output
        _, output = process_pdf(pdf, backend=backend)
        with pymupdf.open(stream=output, filetype='pdf') as doc:
            assert 'Barack Obama' not in doc[0].get_text()
            assert 'London' in doc[0].get_text()
        print(factory.__name__ + ': real model TXT + PDF smoke PASS')


if __name__ == '__main__':
    main()
