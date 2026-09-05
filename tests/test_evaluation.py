from pathlib import Path
import importlib.util
import pytest
from smart_redactor.evaluation import score_documents


def test_exact_metrics_hand_counted():
    gold = [[('PERSON', 0, 4), ('EMAIL', 10, 20)], [('PERSON', 0, 4)]]
    predicted = [[('PERSON', 0, 3), ('EMAIL', 10, 20), ('EMAIL', 10, 20)], [('PERSON', 0, 4)]]
    score = score_documents(gold, predicted)
    assert score['per_type']['PERSON']['tp'] == 1
    assert score['per_type']['PERSON']['fp'] == 1
    assert score['per_type']['PERSON']['fn'] == 1
    assert score['per_type']['PERSON']['f1'] == 0.5
    assert score['micro']['f1'] == pytest.approx(2/3)
    assert score['per_type']['ADDRESS']['f1'] == 0


def test_document_boundary_and_label_mismatch():
    score = score_documents([[('PERSON', 0, 4)], []], [[], [('PERSON', 0, 4)]])
    assert score['micro']['tp'] == 0
    score = score_documents([[('PERSON', 0, 4)]], [[('ADDRESS', 0, 4)]])
    assert score['micro']['fp'] == score['micro']['fn'] == 1
    with pytest.raises(ValueError):
        score_documents([[]], [])


def test_dataset_valid_and_disjoint():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('evaluation_runner', root/'evaluation/run.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    dev, test = [module.load_dataset(root/f'evaluation/{split}.jsonl') for split in ['dev', 'test']]
    assert len(dev) == 6 and len(test) == 24
    assert not {d['text'] for d in dev} & {d['text'] for d in test}
    names = lambda rows: {d['text'][e['start']:e['end']] for d in rows for e in d['entities'] if e['type'] == 'PERSON'}
    assert not names(dev) & names(test)
    assert sum(len(d['entities']) for d in test) == 35
