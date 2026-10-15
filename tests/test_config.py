from pathlib import Path

import pytest

from vid2sub import config as c

ROOT = Path(__file__).resolve().parents[1]


def write(tmp_path, text):
    path = tmp_path / "vid2sub.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_example_file_is_the_starter_and_is_valid(tmp_path):
    assert (ROOT / "vid2sub.example.toml").read_text(encoding="utf-8") == c.STARTER
    cfg = c.load_config(write(tmp_path, c.STARTER))
    assert set(cfg.models) == {"spark-turbo", "spark-gemma", "mac-qwen", "openai-whisper",
                               "openai-gpt"}
    assert c.is_local(cfg.models["spark-turbo"], cfg)
    assert c.is_local(cfg.models["mac-qwen"], cfg)
    assert not c.is_local(cfg.models["openai-whisper"], cfg)


def test_no_file_means_defaults_and_no_models(tmp_path):
    cfg = c.load_config(tmp_path / "missing.toml")
    assert cfg.models == {} and cfg.defaults.targets == ["en"]


def test_an_unknown_key_is_refused_by_name(tmp_path):
    with pytest.raises(c.ConfigError, match="colour"):
        c.load_config(write(tmp_path, "[server]\ncolour = 'blue'\n"))


def test_a_key_value_is_refused_without_echoing_it(tmp_path):
    text = '[endpoints.x]\nbase_url = "https://api.openai.com/v1"\nkey_env = "sk-live-abc123"\n'
    with pytest.raises(c.ConfigError) as err:
        c.load_config(write(tmp_path, text))
    assert "sk-live" not in str(err.value) and "endpoints.x.key_env" in str(err.value)


def test_local_true_needs_a_local_host(tmp_path):
    text = ('[endpoints.cloud]\nbase_url = "https://api.openai.com/v1"\n'
            '[models.m]\nendpoint = "cloud"\nmodel = "whisper-1"\nparser = "openai"\nlocal = true\n')
    with pytest.raises(c.ConfigError, match="local_hosts"):
        c.load_config(write(tmp_path, text))


def test_a_key_over_plain_http_to_the_lan_is_refused(tmp_path):
    text = '[endpoints.lan]\nbase_url = "http://192.168.1.50:9100/v1"\nkey_env = "SPARK_API_KEY"\n'
    with pytest.raises(c.ConfigError, match="https"):
        c.load_config(write(tmp_path, text))


def test_a_model_needs_exactly_one_of_endpoint_or_engine(tmp_path):
    with pytest.raises(c.ConfigError, match="exactly one"):
        c.load_config(write(tmp_path, '[models.m]\nmodel = "x"\n'))


def test_the_config_path_prefers_the_flag_then_the_environment(tmp_path):
    assert c.config_path("~/a.toml", {}) == Path("~/a.toml").expanduser()
    assert c.config_path(None, {"VID2SUB_CONFIG": str(tmp_path / "b.toml")}) == tmp_path / "b.toml"
    assert c.config_path(None, {}).name == "vid2sub.toml"


def test_the_packaged_starter_matches_the_repo_example():
    assert (ROOT / "src" / "vid2sub" / "example.toml").read_text(encoding="utf-8") == c.STARTER


def test_a_key_pasted_into_any_string_field_is_refused_without_echoing_it(tmp_path):
    text = '[models.m]\nendpoint = "x"\nmodel = "sk-live-abc123"\n'
    with pytest.raises(c.ConfigError, match="looks like a key") as err:
        c.load_config(write(tmp_path, text))
    assert "sk-live" not in str(err.value)
