"""Explicit network-enabled setup, never imported by the app."""
from pathlib import Path
from huggingface_hub import snapshot_download

if __name__ == '__main__':
    target = Path(__file__).resolve().parents[1] / 'models' / 'bert-base-NER'
    snapshot_download('dslim/bert-base-NER', revision='d1a3e8f13f8c3566299d95fcfc9a8d2382a9affc', local_dir=target,
                      allow_patterns=['config.json', '*.safetensors', 'tokenizer*',
                                      'vocab.txt', 'special_tokens_map.json'])
    print('Model downloaded to models/bert-base-NER; app inference uses local files only.')
