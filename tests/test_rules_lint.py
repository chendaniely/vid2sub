from vid2sub.subs.lint import lint, looks_hallucinated
from vid2sub.subs.model import Cue
from vid2sub.subs.rules import RULES, cps, rules_for, width_chars


def test_rules_follow_the_netflix_line_widths_per_language():
    assert rules_for("en").max_width == 42
    assert rules_for("ja").max_width == 26
    assert rules_for("zh").max_width == 32 and rules_for("yue").max_width == 32
    assert rules_for("xx") == RULES["en"]
    assert width_chars(rules_for("ja"), cjk=True) == 13


def test_the_rules_hash_changes_when_a_rule_changes():
    en = rules_for("en")
    assert en.sha() == rules_for("en").sha()
    assert en.sha() != rules_for("ja").sha()


def test_reading_speed_ignores_line_breaks():
    assert cps("ab\ncd", 1000) == 4.0


def test_known_hallucinations_are_recognised_across_lines_and_case():
    assert looks_hallucinated("ご視聴\nありがとうございました", "ja")
    assert looks_hallucinated("Thank you\nfor watching!", "en")
    assert looks_hallucinated("Thanks for watching", "ja")  # English phrases count everywhere
    assert not looks_hallucinated("We choose to go to the moon", "en")


def test_lint_flags_width_duration_and_reading_speed():
    rules = rules_for("en")
    cues = [
        Cue(id="ok", start_ms=0, end_ms=2000, text="Fine"),
        Cue(id="wide", start_ms=3000, end_ms=6000, text="x" * 50),
        Cue(id="short", start_ms=7000, end_ms=7300, text="Hi"),
        Cue(id="fast", start_ms=8000, end_ms=9000, text="This is far too much text to read"),
    ]
    flags = lint(cues, rules)
    assert "ok" not in flags
    assert "width" in flags["wide"]
    assert "duration" in flags["short"]
    assert "cps" in flags["fast"]
