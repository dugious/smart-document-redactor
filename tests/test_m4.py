import pytest
from smart_redactor.detection.ner import chunks, detect_all, SpacyBackend, TransformersBackend
from smart_redactor.detection.structured import Candidate
from smart_redactor.schemas import ProcessingError
from smart_redactor.text import process_txt
from smart_redactor.pipeline import process_pdf
from test_m1 import pdf, text


class FakeNer:
    def detect(self, value):
        name = 'Alice Example'
        start = value.index(name)
        return [Candidate('PERSON', start, start+len(name), name, 'spacy')]


def test_person_pdf_txt():
    source = 'Alice Example sent demo@example.com'
    analysis, output = process_txt(source.encode(), backend=FakeNer())
    assert output == b'[PERSON] sent [EMAIL]'
    assert analysis.entities[0].confidence is None
    _, output = process_pdf(pdf([(40, 60, source)]), backend=FakeNer())
    assert 'Alice Example' not in text(output)
    assert 'sent' in text(output)


def test_chunks_cover_every_character():
    source = 'x' * 17001
    windows = list(chunks(source, 8000, 400))
    covered = set()
    for offset, value in windows:
        assert value == source[offset:offset+len(value)]
        covered.update(range(offset, offset+len(value)))
    assert len(covered) == len(source)
    assert list(chunks('')) == []


def test_invalid_ner_fail_closed():
    class Bad:
        def detect(self, value):
            return [Candidate('PERSON', 0, 10000, 'wrong', 'spacy')]
    with pytest.raises(ProcessingError):
        detect_all('hello', Bad())


def test_regex_priority_over_person():
    class BadName:
        def detect(self, value):
            return [Candidate('PERSON', 0, len(value), value, 'spacy')]
    entities = detect_all('demo@example.com', BadName())
    assert len(entities) == 1 and entities[0].type == 'EMAIL'


def test_missing_transformer_model():
    with pytest.raises(ProcessingError, match='unavailable'):
        TransformersBackend('does-not-exist-local-model')


def test_transformer_token_guard_and_absolute_offsets():
    # Exercise real adapter chunk control with fake tokenizer/model: one token/char.
    backend = TransformersBackend.__new__(TransformersBackend)
    backend.limit = 64
    backend.tokenizer = lambda value, **kwargs: {'input_ids': list(range(len(value)+2))}
    def infer(value):
        assert len(value)+2 <= 64
        result = []
        start = value.find('Alice Example')
        if start >= 0:
            result.append({'entity_group': 'PER', 'start': start, 'end': start+13, 'score': 0.9})
        return result
    backend.pipe = infer
    source = 'x ' * 200 + 'Alice Example' + ' y' * 100
    entities = backend.detect(source)
    assert len(entities) == 1
    assert entities[0].start == 400 and entities[0].confidence == 0.9


def test_spacy_chunk_offsets_and_confidence():
    from types import SimpleNamespace
    backend = SpacyBackend.__new__(SpacyBackend)
    def nlp(value):
        pos = value.find('Alice Example')
        return SimpleNamespace(ents=[] if pos < 0 else [SimpleNamespace(label_='PERSON', start_char=pos, end_char=pos+13)])
    backend.nlp = nlp
    source = 'x ' * 3900 + 'Alice Example' + ' y' * 2000
    entities = backend.detect(source)
    assert len(entities) == 1
    assert entities[0].start == 7800 and entities[0].confidence is None
