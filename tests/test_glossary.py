import pytest

from vid2sub.subs.glossary import (
    EMPTY_GLOSSARY,
    GlossaryError,
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
    assert len(chunk_prompt(g, "x" * 1000, cjk=True)) <= 200
    assert len(chunk_prompt(EMPTY_GLOSSARY, "y" * 1000, cjk=False)) == 200
