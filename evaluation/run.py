"""Run from project root: python evaluation/run.py --backend spacy|transformers."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import statistics
import time
from datetime import datetime, timezone
from smart_redactor.detection.ner import SpacyBackend, TransformersBackend, detect_all
from smart_redactor.detection.structured import TYPES
from smart_redactor.evaluation import score_documents


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda: file.read(1024*1024), b''):
            sha.update(block)
    return sha.hexdigest()


def load_dataset(path):
    docs = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    if not docs or len({d['id'] for d in docs}) != len(docs):
        raise ValueError('Dataset empty or IDs duplicated')
    for doc in docs:
        seen = set()
        for e in doc['entities']:
            key = (e['type'], e['start'], e['end'])
            if e['type'] not in TYPES or not 0 <= e['start'] < e['end'] <= len(doc['text']) or key in seen:
                raise ValueError('Invalid gold span')
            seen.add(key)
    return docs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=['spacy', 'transformers'], required=True)
    parser.add_argument('--dataset', default='evaluation/test.jsonl')
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('repeats must be positive')
    docs = load_dataset(args.dataset)
    start = time.perf_counter()
    backend = SpacyBackend() if args.backend == 'spacy' else TransformersBackend()
    load_seconds = time.perf_counter()-start
    # Fixed synthetic warmup, excluded from timings; no test tuning.
    detect_all('Alice Example sent a message.', backend)
    times, predicted = [], None
    for _ in range(args.repeats):
        start = time.perf_counter()
        current = [[(e.type, e.start, e.end) for e in detect_all(d['text'], backend)] for d in docs]
        times.append(time.perf_counter()-start)
        if predicted is not None and current != predicted:
            raise RuntimeError('Nondeterministic predicted spans across repeats')
        predicted = current
    gold = [[(e['type'], e['start'], e['end']) for e in d['entities']] for d in docs]
    model_dir = Path('models/bert-base-NER') if args.backend == 'transformers' else Path(__import__('en_core_web_sm').__file__).parent
    files = sorted(p for p in model_dir.rglob('*') if p.is_file() and '.cache' not in p.parts and '__pycache__' not in p.parts)
    model_hashes = {str(p.relative_to(model_dir)): digest(p) for p in files}
    revisions = set()
    if args.backend == 'transformers':
        for p in (model_dir / '.cache/huggingface/download').glob('*.metadata'):
            revisions.add(p.read_text().splitlines()[0])
    packages = {name: importlib.metadata.version(name) for name in ['spacy', 'transformers', 'torch', 'en-core-web-sm', 'pdfplumber', 'pymupdf']}
    report = {
        'created_utc': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'scope': 'Synthetic text detection only; NOT PDF extraction/redaction timing or real-world accuracy.',
        'dataset': {'file': Path(args.dataset).name, 'sha256': digest(args.dataset), 'documents': len(docs), 'characters': sum(len(d['text']) for d in docs)},
        'model': {'name': 'en_core_web_sm' if args.backend == 'spacy' else 'dslim/bert-base-NER',
                  'revision_evidence': sorted(revisions) if revisions else packages['en-core-web-sm'], 'files_sha256': model_hashes},
        'machine': {'os': platform.platform(), 'python': platform.python_version(), 'cpu': platform.processor(), 'logical_cpus': os.cpu_count(), 'device': 'cpu', 'ram_bytes': None},
        'packages': packages,
        'source_sha256': {str(p): digest(p) for p in sorted(Path('src/smart_redactor/detection').glob('*.py'))},
        'timing': {'model_load_seconds': load_seconds, 'warmup_excluded': True, 'runs_seconds': times, 'median_seconds': statistics.median(times), 'repeats': args.repeats},
        'metrics': score_documents(gold, predicted),
        'policy': 'Exact type/start/end per document; zero denominator -> 0; duplicates deduplicated; structured priority before PERSON; no threshold tuning.'
    }
    if os.name == 'nt':
        import ctypes
        class MemoryStatus(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in ['total', 'available', 'page_total', 'page_available', 'virtual_total', 'virtual_available', 'extended']]
        memory = MemoryStatus(); memory.length = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            report['machine']['ram_bytes'] = memory.total
    folder = Path('evaluation/results'); folder.mkdir(exist_ok=True)
    output = folder / f'{Path(args.dataset).stem}-{args.backend}.json'
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(output), 'metrics': report['metrics'], 'timing': report['timing']}, indent=2))


if __name__ == '__main__':
    main()
