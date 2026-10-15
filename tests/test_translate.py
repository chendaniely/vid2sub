import re

import pytest
from fakes import FakeServer, chat_responder

from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines.clients import KeyRing, RunPolicy
from vid2sub.subs.glossary import EMPTY_GLOSSARY, parse_glossary
from vid2sub.subs.model import Cue
from vid2sub.translate.run import TranslationFailed, make_ask, system_prompt, translate_cues

SOURCE = [Cue(id=f"s{i}", start_ms=i * 2000, end_ms=i * 2000 + 1500, text=f"テキスト{i}")
          for i in range(85)]


def fake_ask(*, fail_sizes=(), empty_for=()):
    calls = []

    def ask(system, prompt, model):
        ids = re.findall(r"^\[(\S+)\] \(max", prompt, flags=re.MULTILINE)
        calls.append((system, prompt, ids))
        order = list(reversed(ids)) if len(ids) in fail_sizes else ids
        items = [{"src": [i], "text": "" if i in empty_for else f"EN {i}"} for i in order]
        return model.model_validate({"items": items})

    return ask, calls


def test_a_track_is_translated_in_batches_with_timing_from_the_source():
    ask, calls = fake_ask()
    out = translate_cues(SOURCE, source_lang="ja", target_track="en", glossary=EMPTY_GLOSSARY,
                         ask=ask)
    assert len(calls) == 3 and [len(c[2]) for c in calls] == [40, 40, 5]
    assert [c.text for c in out[:2]] == ["EN s0", "EN s1"]
    assert (out[3].start_ms, out[3].end_ms, out[3].src) == (6000, 7500, ("s3",))


def test_the_prompt_shows_context_and_limits_and_the_system_prompt_the_glossary():
    ask, calls = fake_ask()
    glossary = parse_glossary('description = "An anime"\n[terms]\n"工藤新一" = "Shinichi Kudo"\n')
    translate_cues(SOURCE, source_lang="ja", target_track="en", glossary=glossary, ask=ask)
    system, second_prompt, _ = calls[1]
    assert "Japanese to English" in system and "工藤新一 → Shinichi Kudo" in system
    assert "An anime" in system
    assert "Earlier lines" in second_prompt and "(max 30 characters)" in second_prompt


def test_a_batch_the_model_gets_wrong_is_split_and_retried():
    ask, calls = fake_ask(fail_sizes={40})
    out = translate_cues(SOURCE, source_lang="ja", target_track="en", glossary=EMPTY_GLOSSARY,
                         ask=ask)
    assert len(out) == 85
    assert [len(c[2]) for c in calls] == [40, 20, 20, 40, 20, 20, 5]


def test_a_single_cue_that_cant_be_translated_fails_loudly():
    ask, _ = fake_ask(empty_for={"s1"})
    with pytest.raises(TranslationFailed, match="s1"):
        translate_cues(SOURCE[:3], source_lang="ja", target_track="en", glossary=EMPTY_GLOSSARY,
                       ask=ask)


def test_only_the_asked_cues_are_translated():
    ask, calls = fake_ask()
    out = translate_cues(SOURCE, source_lang="ja", target_track="en", glossary=EMPTY_GLOSSARY,
                         ask=ask, only=["s1", "s2"])
    assert [c.src for c in out] == [("s1",), ("s2",)]
    assert calls[0][2] == ["s1", "s2"]


def test_chinese_targets_are_told_their_script():
    assert "Traditional Chinese" in system_prompt("ja", "zh-Hant", EMPTY_GLOSSARY)


def test_translation_goes_through_chatlas_with_a_schema_and_thinking_off():
    with FakeServer(responder=chat_responder) as srv:
        cfg = Config(
            endpoints={"spark": Endpoint(base_url=srv.url, key_env="SPARK_API_KEY")},
            models={"gemma": ModelEntry(catalog="gemma-4-26b-a4b", endpoint="spark",
                                        model="gemma-4-26b-a4b", task="translate", local=True,
                                        request_extra={"chat_template_kwargs":
                                                       {"enable_thinking": False}})})
        ask = make_ask("gemma", cfg.models["gemma"], cfg, RunPolicy(),
                       KeyRing(environ={"SPARK_API_KEY": "k"}))
        out = translate_cues(SOURCE[:3], source_lang="ja", target_track="en",
                             glossary=EMPTY_GLOSSARY, ask=ask)
        req = srv.requests[0]
    assert [c.text for c in out] == ["EN s0", "EN s1", "EN s2"]
    assert req.path == "/v1/chat/completions"
    body = req.json()
    assert body["response_format"]["type"] == "json_schema"
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["messages"][0]["role"] == "system"
