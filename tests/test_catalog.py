from vid2sub.catalog import CATALOG, Candidate, readme_table, suggest


def cand(name, catalog, kind="endpoint", available=True, reason="", cloud=False):
    return Candidate(name=name, catalog=catalog, kind=kind, available=available, reason=reason,
                     cloud=cloud)


def test_the_catalog_has_the_models_the_spec_lists():
    for cid in ("qwen3-asr-1.7b", "qwen3-asr-0.6b", "whisper-large-v3", "whisper-large-v3-turbo",
                "openai-whisper-1", "gemma-4-26b-a4b", "qwen3.8-27b", "local-llm", "openai-gpt"):
        assert cid in CATALOG
    assert CATALOG["qwen3-asr-1.7b"].max_chunk_s == 180
    assert CATALOG["openai-whisper-1"].cloud


def test_cantonese_prefers_qwen_and_the_spark_before_the_mac():
    candidates = [cand("mac-qwen", "qwen3-asr-1.7b", kind="in-process"),
                  cand("spark-qwen", "qwen3-asr-1.7b"),
                  cand("spark-turbo", "whisper-large-v3-turbo")]
    assert suggest("yue", candidates, "transcribe", allow_cloud=False).model == "spark-qwen"


def test_an_unavailable_model_is_skipped_with_its_reason():
    candidates = [cand("spark-qwen", "qwen3-asr-1.7b", available=False,
                       reason="Spark not reachable"),
                  cand("spark-turbo", "whisper-large-v3-turbo")]
    s = suggest("yue", candidates, "transcribe", allow_cloud=False)
    assert s.model == "spark-turbo"
    assert ("spark-qwen", "Spark not reachable") in s.considered
    assert "weak" in s.warning


def test_a_cloud_model_needs_the_runs_permission():
    candidates = [cand("openai", "openai-whisper-1", cloud=True)]
    assert suggest("en", candidates, "transcribe", allow_cloud=False).model is None
    assert suggest("en", candidates, "transcribe", allow_cloud=True).model == "openai"


def test_translation_defaults_to_gemma_on_the_spark_not_the_coder():
    candidates = [cand("spark-coder", "qwen3.8-27b"), cand("spark-gemma", "gemma-4-26b-a4b")]
    assert suggest("zh", candidates, "translate", allow_cloud=False).model == "spark-gemma"


def test_the_readme_table_lists_every_catalog_model():
    table = readme_table()
    assert table.startswith("| Model |")
    assert all(entry.title in table for entry in CATALOG.values())
