import pytest

from vid2sub.catalog import CATALOG, Candidate, CatalogEntry, readme_table, suggest


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
    assert len(table.splitlines()) == len(CATALOG) + 2


def test_the_readme_table_escapes_pipes_and_keeps_each_row_on_one_line(monkeypatch):
    entry = CatalogEntry("x-pipe", "translate", "A | B", good_for="line one\nline two",
                         weak="", runs_on="somewhere", install="nothing")
    monkeypatch.setitem(CATALOG, "x-pipe", entry)
    table = readme_table()
    assert "| A \\| B |" in table
    assert "line one line two" in table
    assert len(table.splitlines()) == len(CATALOG) + 2


def test_the_cloud_gate_uses_the_catalog_flag_when_the_candidate_forgets_it():
    candidates = [cand("openai", "openai-whisper-1", cloud=False)]
    s = suggest("en", candidates, "transcribe", allow_cloud=False)
    assert s.model is None
    assert ("openai", "a cloud model: needs --allow-cloud") in s.considered


def test_an_unknown_task_is_refused_by_name():
    with pytest.raises(ValueError, match="transcription"):
        suggest("en", [], "transcription", allow_cloud=False)


def test_a_language_without_a_route_uses_the_english_route_and_says_so():
    candidates = [cand("spark-turbo", "whisper-large-v3-turbo")]
    s = suggest("fr", candidates, "transcribe", allow_cloud=False)
    assert s.model == "spark-turbo"
    assert "no route for fr" in s.warning


def test_translation_has_no_qwen_coder_route_and_the_coder_is_explained():
    candidates = [cand("spark-coder", "qwen3.8-27b")]
    s = suggest("zh", candidates, "translate", allow_cloud=False)
    assert s.model is None
    assert ("spark-coder",
            "not in the translate route for zh; choose it with --model") in s.considered


def test_a_weak_pairing_warns_that_the_model_is_weak():
    candidates = [cand("spark-turbo", "whisper-large-v3-turbo")]
    s = suggest("zh", candidates, "transcribe", allow_cloud=False)
    assert s.model == "spark-turbo"
    assert "weak" in s.warning


def test_an_unavailable_spark_qwen_falls_back_to_the_mac_qwen_for_cantonese():
    candidates = [cand("spark-qwen", "qwen3-asr-1.7b", available=False,
                       reason="Spark not reachable"),
                  cand("mac-qwen", "qwen3-asr-1.7b", kind="in-process")]
    assert suggest("yue", candidates, "transcribe", allow_cloud=False).model == "mac-qwen"
