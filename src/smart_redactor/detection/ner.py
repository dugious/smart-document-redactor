"""Local-only model adapters. Downloads belong to a separate setup command."""
from pathlib import Path
from typing import Protocol
from smart_redactor.schemas import ProcessingError
from smart_redactor.detection.structured import Candidate, detect_structured, resolve_overlaps


class NerBackend(Protocol):
    def detect(self, text: str) -> list[Candidate]: ...


def chunks(text: str, size: int = 1600, overlap: int = 200):
    if not 0 <= overlap < size:
        raise ValueError('Invalid chunk configuration')
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        yield start, text[start:end]
        if end == len(text):
            break
        start = end - overlap


def detect_all(text: str, backend: NerBackend | None = None) -> list[Candidate]:
    candidates = detect_structured(text)
    if backend is not None:
        try:
            people = backend.detect(text)
            for c in people:
                if (c.type != 'PERSON' or not 0 <= c.start < c.end <= len(text)
                        or text[c.start:c.end] != c.text or c.source not in {'spacy', 'transformers'}
                        or (c.confidence is not None and not 0 <= c.confidence <= 1)):
                    raise ProcessingError('Invalid NER result.')
            candidates.extend(people)
        except ProcessingError:
            raise
        except Exception:
            raise ProcessingError('NER inference failed; no complete analysis is available.') from None
    return resolve_overlaps(candidates)


class SpacyBackend:
    def __init__(self, model: str = 'en_core_web_sm'):
        try:
            import spacy
            self.nlp = spacy.load(model)
            if 'ner' not in self.nlp.pipe_names:
                raise ValueError('Missing NER')
        except Exception:
            raise ProcessingError('spaCy model unavailable. Install dependencies and download the model explicitly first.') from None

    def detect(self, text: str) -> list[Candidate]:
        results = []
        for offset, chunk in chunks(text, size=8000, overlap=400):
            for ent in self.nlp(chunk).ents:
                if ent.label_ == 'PERSON':
                    results.append(Candidate('PERSON', offset + ent.start_char, offset + ent.end_char,
                                             text[offset + ent.start_char:offset + ent.end_char], 'spacy', None))
        return resolve_overlaps(results)


class TransformersBackend:
    def __init__(self, model: str = 'models/bert-base-NER'):
        try:
            from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
            path = Path(model)
            if not path.is_dir():
                raise ValueError('Local directory required')
            tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, use_fast=True, trust_remote_code=False)
            ner_model = AutoModelForTokenClassification.from_pretrained(str(path), local_files_only=True,
                                                                         trust_remote_code=False, use_safetensors=True)
            if not tokenizer.is_fast:
                raise ValueError('Fast tokenizer required')
            limit = min(tokenizer.model_max_length, ner_model.config.max_position_embeddings)
            if limit < 32 or limit > 100_000:
                raise ValueError('Unsupported token limit')
            self.limit = limit
            self.tokenizer = tokenizer
            self.pipe = pipeline('token-classification', model=ner_model, tokenizer=tokenizer,
                                 aggregation_strategy='simple', device=-1)
        except Exception:
            raise ProcessingError('Transformers local model unavailable. Download a safetensors model explicitly first.') from None

    def detect(self, text: str) -> list[Candidate]:
        results = []
        # Token-count guard plus shrinking windows: never hand an oversized chunk
        # to pipeline (which would silently truncate). Overlap provides context.
        start = 0
        while start < len(text):
            end = min(start + 1600, len(text))
            while len(self.tokenizer(text[start:end], add_special_tokens=True, truncation=False)['input_ids']) > self.limit:
                end = start + (end - start) // 2
                if end <= start:
                    raise ProcessingError('Unable to fit NER chunk into model context.')
            for ent in self.pipe(text[start:end]):
                if ent['entity_group'] in {'PER', 'PERSON'}:
                    a, b = start + int(ent['start']), start + int(ent['end'])
                    results.append(Candidate('PERSON', a, b, text[a:b], 'transformers', float(ent['score'])))
            if end == len(text):
                break
            start = end - min(200, (end-start)//4)
        return resolve_overlaps(results)
