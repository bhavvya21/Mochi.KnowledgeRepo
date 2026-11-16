"""Opt-in real neural-model test. CI runs this on Linux, without Ollama."""
import os
import pytest
from mochi.models import LocalModels
from mochi.config import Settings


@pytest.mark.skipif(os.getenv('RUN_MODEL_TESTS')!='1',reason='Opt-in model download and native ONNX runtime')
def test_real_embeddings_and_cross_encoder():
    models=LocalModels(Settings())
    vectors=models.embed(['The launch is on May 14.','Penguins live in Antarctica.'])
    assert len(vectors)==2 and len(vectors[0])==384
    assert vectors[0]!=vectors[1]
    scores=models.rerank('When is the launch?',['The launch is on May 14.','Penguins live in Antarctica.'])
    assert len(scores)==2 and scores[0]>scores[1]
