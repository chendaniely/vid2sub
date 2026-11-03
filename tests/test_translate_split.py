import re

import pytest

from vid2sub.subs import text as subs_text
from vid2sub.subs import translate_shape as ts
from vid2sub.subs.glossary import EMPTY_GLOSSARY
from vid2sub.subs.model import Cue, check_track
from vid2sub.subs.text import unwrap, width
from vid2sub.translate.run import translate_cues

# Made-up lines in the shape of M1's exit-test episode (spec §13.4, S68): its largest English
# item was 218 characters, and one item covered two cues 27 seconds apart.
LONGEST = ("I told you this morning that the shop would close early, but you never listen to me. "
           "Now the shelves are empty, the rent is due on Friday, and we still have to pay the "
           "drivers before they leave for the harbour tonight.")
FIVE = [(60_000, 62_400, "我早上就跟你说了今天店要早关"), (62_500, 65_100, "可你就是不听"),
        (65_200, 67_000, "现在货架都空了"), (67_100, 69_800, "房租礼拜五就要交"),
        (69_900, 72_300, "司机今晚去码头之前我们还得把钱付了")]
APART = [(179_100, 180_500, "你先别走"), (207_400, 210_100, "我去拿钥匙马上回来")]
ACROSS_THE_SILENCE = "Don't go yet. I'll get the keys and come right back."
TOO_LONG = ("Pack the van, lock the back door and leave the keys with the old man at the corner, "
            "because nobody else will be here when the lorry comes back at six.")


def cues(spans, prefix: str = "s", shift: int = 0) -> dict[str, Cue]:
    return {f"{prefix}{i}": Cue(id=f"{prefix}{i}", start_ms=s + shift, end_ms=e + shift, text=t)
            for i, (s, e, t) in enumerate(spans)}


def split(source: dict[str, Cue], text: str, track: str = "en") -> list[Cue]:
    """The cues one item covering every cue of `source` becomes."""
    items = ts.split_items([ts.Item(tuple(source), text)], source, track)
    return ts.assemble(items, source, track, set())


def shown(out: list[Cue]) -> list[tuple[int, int, tuple[str, ...] | None, str]]:
    return [(c.start_ms, c.end_ms, c.src, c.text) for c in out]


def test_a_218_character_item_goes_back_to_its_five_cues_at_its_sentence_and_clause_ends():
    source = cues(FIVE)
    out = split(source, LONGEST)
    assert shown(out) == [
        (60_000, 62_400, ("s0",), "I told you this morning that\nthe shop would close early,"),
        (62_500, 65_100, ("s1",), "but you never listen to me."),
        (65_200, 67_000, ("s2",), "Now the shelves are empty,"),
        (67_100, 69_800, ("s3",), "the rent is due on Friday,"),
        (69_900, 72_300, ("s4",), ("and we still have to pay the drivers\n"
                                   "before they leave for the harbour tonight."))]
    assert " ".join(unwrap(c.text) for c in out) == LONGEST  # nothing dropped


def test_an_item_across_a_27_second_silence_is_shown_only_while_each_of_its_cues_is_spoken():
    out = split(cues(APART), ACROSS_THE_SILENCE)
    assert shown(out) == [(179_100, 180_500, ("s0",), "Don't go yet."),
                          (207_400, 210_100, ("s1",), "I'll get the keys and come right back.")]


def test_an_item_within_its_limit_over_cues_close_together_stays_one_cue():
    source = cues([(0, 2000, "你要去哪儿"), (2300, 4500, "这么晚了")])
    assert shown(split(source, "Where are you going this late?")) == [
        (0, 4500, ("s0", "s1"), "Where are you going this late?")]


def test_an_item_that_fits_two_lines_but_reads_fast_stays_one_cue():
    # 56 characters in 2.6 s is 21.5 characters a second, over English's 20: reading speed is a
    # lint, and never splits a cue (spec §12.2).
    source = cues([(0, 1200, "你去哪儿"), (1400, 2600, "这么晚了")])
    (out,) = split(source, "Where are you off to at this hour of the night, so late?")
    assert out.src == ("s0", "s1") and out.text.count("\n") == 1


@pytest.mark.parametrize(("gap", "parts"), [(1000, 1), (1001, 2)])
def test_cues_more_than_a_second_apart_are_split_and_a_second_apart_are_not(gap, parts):
    assert ts.SPLIT_GAP_MS == 1000
    source = cues([(0, 2000, "你要去哪儿"), (2000 + gap, 4500 + gap, "这么晚了")])
    assert len(split(source, "Where are you going? It's so late.")) == parts


def test_an_item_lasting_longer_than_seven_seconds_goes_back_to_its_cues():
    source = cues([(0, 3000, "等等"), (3500, 6000, "我还没说完"), (6500, 9000, "听我说")])
    assert [c.text for c in split(source, "Wait, I'm not done. Listen to me.")] == [
        "Wait,", "I'm not done.", "Listen to me."]


def test_a_chinese_target_is_split_at_its_full_stop_and_its_lines_keep_chinese_rules():
    source = cues([(0, 2500, "I can't find my phone anywhere, or my wallet."),
                   (2600, 5200, "Did you leave them in the car again? We have to go back.")])
    out = split(source, "我到处都找不到我的手机，钱包也不见了。"
                        "你是不是又把它们落在车里了？我们得马上回去找。", "zh-Hans")
    assert shown(out) == [(0, 2500, ("s0",), "我到处都找不到我的\n手机，钱包也不见了"),
                          (2600, 5200, ("s1",), "你是不是又把它们落在车\n里了？我们得马上回去找")]
    assert all(width(line) <= 32 for c in out for line in c.text.split("\n"))


def test_each_part_records_only_its_own_cue_so_only_the_part_whose_source_changed_goes_stale():
    source = cues(APART)
    first, second = split(source, ACROSS_THE_SILENCE)
    assert first.src_sha == ts.src_sha(["你先别走"])
    assert second.src_sha == ts.src_sha(["我去拿钥匙马上回来"])
    edited = dict(source, s1=source["s1"].model_copy(update={"text": "我去拿钥匙"}))
    assert ts.stale_ids([first, second], edited) == {second.id}
    assert ts.untranslated(list(source), [first, second]) == []


def test_a_sentence_that_ends_inside_quotes_is_still_a_sentence_end():
    source = cues([(0, 2000, "她跟我说别再回来"), (5000, 7000, "我就没再说什么")])
    assert [c.text for c in split(source, 'She told me, "Never come back here." So I left it '
                                          "at that.")] == [
        'She told me, "Never come back here."', "So I left it at that."]


def test_a_word_wider_than_a_line_keeps_a_line_of_its_own():
    assert subs_text.fill("Pneumonoultramicroscopicsilicovolcanoconiosis is a long word", 20) == [
        "Pneumonoultramicroscopicsilicovolcanoconiosis", "is a long word"]


def test_a_one_cue_translation_too_long_for_two_lines_is_wrapped_in_more_never_cut():
    (out,) = split(cues([(0, 6000, "把车装好")]), TOO_LONG)
    lines = out.text.split("\n")
    assert len(lines) == 4 and all(width(line) <= 42 for line in lines)
    assert unwrap(out.text) == TOO_LONG


def test_an_item_with_fewer_places_to_break_than_cues_is_split_at_the_widest_gaps_first():
    source = cues([(0, 1500, "等等"), (1600, 3000, "别走"), (30_000, 31_500, "好吧")])
    assert shown(split(source, "Wait, okay.")) == [(0, 3000, ("s0", "s1"), "Wait,"),
                                                   (30_000, 31_500, ("s2",), "okay.")]


def test_an_item_with_nowhere_to_break_stays_whole():
    assert shown(split(cues(APART), "Wait!")) == [(179_100, 210_100, ("s0", "s1"), "Wait!")]


def test_every_english_cue_of_an_episode_keeps_two_lines_of_42_and_at_most_seven_seconds():
    # Twelve cues as the model grouped M1's episode: three cues as one 150-character item, a
    # short one, two across a 27-second silence, five as the 218-character item, a short one.
    source = {**cues([(57_000, 59_400, "装车"), (59_500, 62_000, "锁好后门"),
                      (62_100, 64_800, "把钥匙给街角的老人")]),
              **cues([(65_600, 66_800, "快点")], prefix="t"),
              **cues(APART, prefix="u"), **cues(FIVE, prefix="v", shift=240_000),
              **cues([(313_000, 314_500, "走吧")], prefix="w")}
    groups = [(["s0", "s1", "s2"], TOO_LONG), (["t0"], "Hurry up."),
              (["u0", "u1"], ACROSS_THE_SILENCE), ([f"v{i}" for i in range(5)], LONGEST),
              (["w0"], "Let's go.")]

    def ask(system, prompt, model):
        asked = re.findall(r"^\[(\S+)\] \(max", prompt, flags=re.MULTILINE)
        assert asked == list(source)
        return model.model_validate({"items": [{"src": g, "text": t} for g, t in groups]})

    out = translate_cues(list(source.values()), source_lang="zh", target_track="en",
                         glossary=EMPTY_GLOSSARY, ask=ask)
    check_track(out)
    assert [c.src for c in out] == [(cid,) for cid in source]
    for c in out:
        lines = c.text.split("\n")
        assert len(lines) <= 2 and all(width(line) <= 42 for line in lines), c.text
        assert c.end_ms - c.start_ms <= 7000
    assert " ".join(unwrap(c.text) for c in out) == " ".join(t for _, t in groups)
