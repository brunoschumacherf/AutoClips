import numpy as np

from ai_engine.providers import Heuristic, provider


def test_huggingface_adapter_scores_and_falls_back(monkeypatch, settings):
    settings.SEMANTIC_PROVIDER = "huggingface"
    settings.SEMANTIC_MODEL = "local-test"

    class Encoder:
        def encode(self, input_text, normalize_embeddings):
            assert normalize_embeddings
            return np.eye(2) if isinstance(input_text, tuple) else np.array([1, 0])

    monkeypatch.setattr("ai_engine.providers.sentence_encoder", lambda name: Encoder())
    assert provider().score("Momento importante!") == 100

    def fail(name):
        raise OSError

    monkeypatch.setattr("ai_engine.providers.sentence_encoder", fail)
    excerpt = "Momento importante!"
    assert provider().score(excerpt) == Heuristic().score(excerpt)
