from pathlib import Path

from vid2sub.catalog import readme_table

README = Path(__file__).resolve().parents[1] / "README.md"


def test_the_readme_model_table_is_the_catalog():
    text = README.read_text(encoding="utf-8")
    start, end = "<!-- models:start -->\n", "<!-- models:end -->"
    assert start in text and end in text, "README needs the models markers"
    assert text.split(start, 1)[1].split(end, 1)[0] == readme_table(), \
        "README's model table is stale: run `make readme`"
