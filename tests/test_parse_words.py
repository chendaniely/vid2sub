from vid2sub.parse.words import attach_punctuation, fill_untimed, ms, tokens_to_words


def test_seconds_become_milliseconds_and_junk_becomes_none():
    assert ms(1.2345) == 1234 or ms(1.2345) == 1235
    assert ms(None) is None and ms(-1) is None and ms("x") is None


def test_english_tokens_merge_into_words_on_the_leading_space():
    words = tokens_to_words([(" Hel", 0, 200, 0.9), ("lo", 200, 400, 0.5), (",", 400, 420, 0.8),
                             (" world", 500, 900, 0.95)])
    assert [w.text for w in words] == [" Hello,", " world"]
    assert (words[0].start_ms, words[0].end_ms, words[0].prob) == (0, 420, 0.5)


def test_cjk_tokens_stay_separate_words_and_latin_inside_cjk_keeps_its_space():
    words = tokens_to_words([("我", 0, 100, None), ("哋", 100, 200, None), (" shop", 200, 300, None),
                             ("ping", 300, 400, None), ("啦", 400, 500, None)])
    assert [w.text for w in words] == ["我", "哋", " shopping", "啦"]


def test_untimed_words_sit_at_the_previous_end_and_are_marked():
    words = fill_untimed([["a", 100, 200, None], ["b", None, None, None], ["c", 300, 250, None]],
                         start_ms=50)
    assert [(w.start_ms, w.end_ms, w.timed) for w in words] == [
        (100, 200, True), (200, 200, False), (200, 200, False)]


def test_punctuation_and_spaces_from_the_text_attach_to_aligned_units():
    words = attach_punctuation("你好，世界。", [("你", 0, 1), ("好", 1, 2), ("世", 2, 3), ("界", 3, 4)])
    assert [w.text for w in words] == ["你", "好，", "世", "界。"]
    words = attach_punctuation(" Hello, world.", [("hello", 0, 5), ("world", 6, 9)])
    assert [w.text for w in words] == [" Hello,", " world."]
    words = attach_punctuation("他说：“你好”", [("他", 0, 1), ("说", 1, 2), ("你", 2, 3), ("好", 3, 4)])
    assert [w.text for w in words] == ["他", "说：", "“你", "好”"]


def test_a_unit_missing_from_the_text_gives_none():
    assert attach_punctuation("abc", [("zzz", 0, 1)]) is None
