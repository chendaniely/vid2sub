import pytest

from vid2sub.subs.glossary import (
    EMPTY_GLOSSARY,
    Glossary,
    GlossaryError,
    add_terms,
    chunk_prompt,
    parse_glossary,
    prompt_sha,
    vocabulary_prompt,
)

TOML = '''
description = "Detective Conan, a Japanese anime"
[terms]
"工藤新一" = "Shinichi Kudo"
"毛利蘭" = "Ran Mouri"
'''


def test_a_glossary_file_reads_its_description_and_term_pairs():
    g = parse_glossary(TOML)
    assert g.description == "Detective Conan, a Japanese anime"
    assert g.terms == (("工藤新一", "Shinichi Kudo"), ("毛利蘭", "Ran Mouri"))
    assert g.source_terms() == ["工藤新一", "毛利蘭"]


def test_the_glossary_hash_is_stable_and_empty_for_no_glossary():
    assert parse_glossary(TOML).sha() == parse_glossary(TOML).sha()
    assert len(parse_glossary(TOML).sha()) == 8
    assert EMPTY_GLOSSARY.sha() == ""
    assert parse_glossary(TOML.replace("Ran", "Rachel")).sha() != parse_glossary(TOML).sha()


@pytest.mark.parametrize("text, message", [
    ("nonsense = [", "isn't valid TOML"),
    ('colour = "x"', "unknown glossary key"),
    ("[terms]\na = 1", "pairs"),
])
def test_a_bad_glossary_says_what_is_wrong(text, message):
    with pytest.raises(GlossaryError, match=message):
        parse_glossary(text)


def test_the_vocabulary_prompt_is_a_plain_list_not_instructions():
    assert vocabulary_prompt(["Quarto", " pixi ", ""]) == "Quarto, pixi."
    assert vocabulary_prompt([]) == ""
    assert prompt_sha("") == "" and len(prompt_sha("a")) == 8


def test_a_chunk_prompt_puts_the_glossary_first_then_the_previous_words():
    g = parse_glossary(TOML)
    prompt = chunk_prompt(g, "and then he said hello", cjk=False)
    assert prompt.startswith("工藤新一, 毛利蘭.")
    assert prompt.endswith("and then he said hello")


def test_a_chunk_prompt_stays_within_its_budget():
    g = parse_glossary("[terms]\n" + "\n".join(f'"term{i}" = "t"' for i in range(200)))
    assert len(chunk_prompt(g, "x" * 1000, cjk=True)) <= 100
    assert len(chunk_prompt(EMPTY_GLOSSARY, "y" * 1000, cjk=False)) == 200


def test_a_cjk_chunk_prompt_fits_whispers_window_with_the_vocabulary_first():
    g = parse_glossary(TOML)
    prompt = chunk_prompt(g, "新一は蘭と一緒に事件を解決した。" * 30, cjk=True)
    assert len(prompt) <= 100
    assert prompt.startswith("工藤新一, 毛利蘭. ")
    assert prompt.endswith("事件を解決した。")


@pytest.mark.parametrize("cjk, budget", [(True, 100), (False, 600)])
def test_a_vocabulary_longer_than_the_budget_is_cut_to_it_and_no_tail_is_added(cjk, budget):
    g = parse_glossary("[terms]\n" + "\n".join(f'"名前{i}" = "n"' for i in range(200)))
    vocab = vocabulary_prompt(g.source_terms())
    assert len(vocab) > budget
    assert chunk_prompt(g, "前の話の終わり", cjk=cjk) == vocab[:budget]


# Phase 2, Task 6: the editor's Save adds terms (spec §16; the plan's Decision 5)


def test_adding_terms_keeps_the_description_the_terms_and_the_comments():
    text = "# names from the first season\n" + TOML + "# more to come\n"
    out, kept = add_terms(text, {"阿笠博士": "Professor Agasa"})
    assert out == text + '"阿笠博士" = "Professor Agasa"\n' and kept == []
    assert parse_glossary(out) == Glossary("Detective Conan, a Japanese anime", (
        ("工藤新一", "Shinichi Kudo"), ("毛利蘭", "Ran Mouri"), ("阿笠博士", "Professor Agasa")))


def test_adding_to_no_glossary_starts_one_with_a_terms_table():
    assert add_terms("", {" 工藤新一 ": "Shinichi Kudo"}) == (
        '[terms]\n"工藤新一" = "Shinichi Kudo"\n', [])


def test_adding_to_a_glossary_with_only_a_description_gives_it_a_terms_table():
    out, _ = add_terms('description = "A show"', {"a": "b"})
    assert out == 'description = "A show"\n\n[terms]\n"a" = "b"\n'
    assert parse_glossary(out) == Glossary("A show", (("a", "b"),))


def test_a_file_with_windows_line_ends_keeps_them():
    out, _ = add_terms('[terms]\r\n"a" = "b"\r\n', {"c": "d"})
    assert out == '[terms]\r\n"a" = "b"\r\n"c" = "d"\r\n'


def test_a_term_already_there_is_left_and_one_with_another_translation_is_reported():
    out, kept = add_terms(TOML, {"工藤新一": "Shinichi Kudo", "毛利蘭": "Rachel Moore"})
    assert out == TOML and kept == ["毛利蘭"]


def test_terms_with_quotes_backslashes_and_control_characters_round_trip():
    adds = {'say "hi"': "back\\slash", "tab\there": "bell\x07", "ü ✨": "ok"}
    out, _ = add_terms("", adds)
    assert dict(parse_glossary(out).terms) == adds


def test_a_term_or_translation_with_no_text_is_refused():
    with pytest.raises(GlossaryError, match="both need text"):
        add_terms(TOML, {"x": "  "})


def test_a_glossary_written_as_an_inline_table_is_refused_rather_than_rewritten():
    with pytest.raises(GlossaryError, match="add them by hand"):
        add_terms('terms = { "a" = "b" }\n', {"c": "d"})


def test_a_glossary_that_isnt_toml_is_refused():
    with pytest.raises(GlossaryError, match="isn't valid TOML"):
        add_terms("nonsense = [", {"c": "d"})
