"""Tests for the metrics module.

The central regression guarded here: WER must be a genuine *word* level rate.
An earlier implementation computed it with a character-level edit distance over
whitespace-joined tokens, which made WER numerically identical to CER for every
input and therefore worthless as a second signal.
"""

from __future__ import annotations

import unicodedata

import pytest

from mlocr_bench.metrics import (
    accuracy_from_cer,
    cer,
    levenshtein,
    mean,
    normalize_text,
    score_sample,
    wer,
)


class TestLevenshtein:
    def test_identical(self):
        assert levenshtein("abc", "abc") == 0

    def test_empty(self):
        assert levenshtein("", "abc") == 3
        assert levenshtein("abc", "") == 3
        assert levenshtein("", "") == 0

    def test_single_edits(self):
        assert levenshtein("abc", "abd") == 1      # substitution
        assert levenshtein("abc", "abcd") == 1     # insertion
        assert levenshtein("abcd", "abc") == 1     # deletion

    def test_symmetry(self):
        assert levenshtein("kitten", "sitting") == levenshtein("sitting", "kitten") == 3

    def test_operates_on_word_sequences(self):
        assert levenshtein(["a", "b", "c"], ["a", "x", "c"]) == 1
        assert levenshtein(["one", "two"], ["one", "two", "three"]) == 1


class TestCER:
    def test_perfect(self):
        assert cer("hello", "hello") == 0.0

    def test_one_of_five_chars(self):
        assert cer("hello", "hallo") == pytest.approx(20.0)

    def test_empty_reference(self):
        assert cer("", "") == 0.0
        assert cer("", "spurious") == 100.0

    def test_total_miss_is_capped(self):
        assert cer("abc", "") == 100.0

    def test_clamping(self):
        # Hypothesis far longer than reference: clamped view hides the extent.
        assert cer("ab", "ab" * 50) == 100.0
        assert cer("ab", "ab" * 50, clamp=False) > 100.0


class TestWER:
    def test_perfect(self):
        assert wer("the quick brown fox", "the quick brown fox") == 0.0

    def test_one_of_four_words(self):
        assert wer("the quick brown fox", "the quick brown cat") == pytest.approx(25.0)

    def test_is_word_level_not_character_level(self):
        """The key regression: WER and CER must be independent signals."""
        reference = "the quick brown fox"
        hypothesis = "the quick brown cat"
        assert wer(reference, hypothesis) == pytest.approx(25.0)
        assert cer(reference, hypothesis) == pytest.approx(15.79, abs=0.01)
        assert wer(reference, hypothesis) != pytest.approx(cer(reference, hypothesis))

    def test_word_insertion_and_deletion(self):
        assert wer("a b c", "a b") == pytest.approx(100 / 3, abs=0.01)
        assert wer("a b", "a b c") == pytest.approx(50.0)

    @pytest.mark.parametrize("language", ["zh", "zh-Hant", "ja", "th", "km", "lo", "my"])
    def test_none_for_spaceless_scripts(self, language):
        """WER is not meaningful without word delimiters — must be None, not 0/100."""
        assert wer("你好世界", "你好世堺", language=language) is None

    def test_applicable_for_spaced_languages(self):
        assert wer("selamat pagi dunia", "selamat pagi dunia", language="id") == 0.0

    def test_empty_reference(self):
        assert wer("", "", language="en") == 0.0
        assert wer("", "junk", language="en") == 100.0


class TestNormalisation:
    # Devanagari has no precomposed codepoints, so NFD == NFC there. Vietnamese
    # and Hangul do decompose, and both are in this benchmark's language set.
    @pytest.mark.parametrize("text", ["Tiếng Việt", "안녕하세요", "café"])
    def test_nfkc_unifies_equivalent_encodings(self, text):
        decomposed = unicodedata.normalize("NFD", text)
        assert text != decomposed                      # different codepoints ...
        assert normalize_text(text) == normalize_text(decomposed)  # ... same after NFKC

    @pytest.mark.parametrize(
        "text,language", [("Tiếng Việt", "vi"), ("안녕하세요", "ko"), ("नमस्ते", "hi")]
    )
    def test_normalised_scoring_is_not_penalised(self, text, language):
        """A visually identical prediction must not be counted as an error."""
        decomposed = unicodedata.normalize("NFD", text)
        assert score_sample(text, decomposed, language=language).cer == 0.0

    def test_unnormalised_comparison_would_penalise(self):
        """Shows why normalisation is on by default."""
        text = "Tiếng Việt"
        decomposed = unicodedata.normalize("NFD", text)
        assert cer(text, decomposed) > 0.0                                  # raw
        assert score_sample(text, decomposed, language="vi").cer == 0.0     # normalised

    def test_whitespace_collapsed(self):
        assert normalize_text("a   b\n\tc") == "a b c"

    def test_casefold_optional(self):
        assert normalize_text("ABC", casefold=True) == "abc"
        assert normalize_text("ABC") == "ABC"


class TestAccuracy:
    def test_complement_of_cer(self):
        assert accuracy_from_cer(0.0) == 100.0
        assert accuracy_from_cer(25.0) == 75.0

    def test_floored_at_zero(self):
        assert accuracy_from_cer(150.0) == 0.0


class TestScoreSample:
    def test_fields_populated(self):
        m = score_sample("hello world", "hello world", language="en")
        assert (m.cer, m.accuracy, m.wer) == (0.0, 100.0, 0.0)
        assert m.ref_chars == m.hyp_chars == 11

    def test_spaceless_language_reports_no_wer(self):
        assert score_sample("你好世界", "你好世界", language="zh").wer is None


class TestMean:
    def test_ignores_none(self):
        assert mean([1.0, None, 3.0]) == 2.0

    def test_all_none(self):
        assert mean([None, None]) is None

    def test_empty(self):
        assert mean([]) is None
