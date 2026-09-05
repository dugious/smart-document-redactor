"""Strict entity-level metrics; never includes document text in reports."""
from smart_redactor.detection.structured import TYPES


def counts_to_metrics(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {'tp': tp, 'fp': fp, 'fn': fn, 'support': tp+fn,
            'precision': precision, 'recall': recall,
            'f1': 2*precision*recall/(precision+recall) if precision+recall else 0.0}


def score_documents(gold: list[list[tuple]], predicted: list[list[tuple]]) -> dict:
    if len(gold) != len(predicted):
        raise ValueError('Document count mismatch')
    counts = {kind: [0, 0, 0] for kind in TYPES}
    for expected, actual in zip(gold, predicted):
        g, p = set(expected), set(actual)
        if any(e[0] not in TYPES for e in g | p):
            raise ValueError('Unknown entity type')
        for kind in TYPES:
            counts[kind][0] += sum(e[0] == kind for e in g & p)
            counts[kind][1] += sum(e[0] == kind for e in p - g)
            counts[kind][2] += sum(e[0] == kind for e in g - p)
    return {'per_type': {k: counts_to_metrics(*v) for k, v in counts.items()},
            'micro': counts_to_metrics(*(sum(v[i] for v in counts.values()) for i in range(3)))}
