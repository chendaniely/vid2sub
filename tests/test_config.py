from pathlib import Path
from types import SimpleNamespace

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


def test_a_key_pasted_as_a_table_key_is_refused_without_echoing_it(tmp_path):
    with pytest.raises(c.ConfigError, match="a key in server looks like a key") as err:
        c.load_config(write(tmp_path, '[server]\n"sk-live-abc123" = 1\n'))
    assert "sk-live" not in str(err.value)


def test_a_long_unknown_key_is_neither_named_nor_echoed(tmp_path):
    token = "a" * 40
    with pytest.raises(c.ConfigError, match="an unknown key in server") as err:
        c.load_config(write(tmp_path, f'[server]\n"{token}" = 1\n'))
    assert token not in str(err.value)


def test_a_catalog_id_that_is_a_token_is_not_echoed(tmp_path):
    token = "a" * 40
    text = f'[models.m]\ncatalog = "{token}"\nendpoint = "x"\nmodel = "m"\n'
    with pytest.raises(c.ConfigError, match="not a catalog id") as err:
        c.load_config(write(tmp_path, text))
    assert token not in str(err.value)


def test_an_endpoint_name_that_is_a_token_is_not_echoed(tmp_path):
    token = "a" * 40
    text = f'[models.m]\nendpoint = "{token}"\nmodel = "m"\nparser = "openai"\n'
    with pytest.raises(c.ConfigError, match="no endpoint by that name") as err:
        c.load_config(write(tmp_path, text))
    assert token not in str(err.value)


def test_a_target_that_is_a_token_is_not_echoed(tmp_path):
    token = "a" * 40
    with pytest.raises(c.ConfigError, match="not a known target track") as err:
        c.load_config(write(tmp_path, f'[defaults]\ntargets = ["{token}"]\n'))
    assert token not in str(err.value)


def test_a_model_table_named_with_a_token_is_not_echoed(tmp_path):
    token = "a" * 40
    text = f'[models.{token}]\nendpoint = "x"\nmodel = "m"\nparser = "openai"\n'
    with pytest.raises(c.ConfigError, match="no endpoint by that name") as err:
        c.load_config(write(tmp_path, text))
    assert token not in str(err.value)


def test_a_base_url_with_credentials_is_refused_without_echoing_them(tmp_path):
    text = '[endpoints.x]\nbase_url = "https://user:tok123@a.b/v1"\n'
    with pytest.raises(c.ConfigError, match="must not contain a user name or password") as err:
        c.load_config(write(tmp_path, text))
    assert "tok123" not in str(err.value)


def test_the_windows_config_falls_back_to_appdata_roaming_when_appdata_is_unset(monkeypatch):
    # Patch only config's view of `os`: a global os.name change breaks pathlib on this machine.
    monkeypatch.setattr(c, "os", SimpleNamespace(name="nt"))
    expected = Path.home() / "AppData" / "Roaming" / "vid2sub" / "vid2sub.toml"
    assert c.config_path(None, {}) == expected


def test_a_relative_xdg_config_home_is_ignored_for_the_default_path():
    assert c.config_path(None, {"XDG_CONFIG_HOME": "rel"}).is_absolute()
