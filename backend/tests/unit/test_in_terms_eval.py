"""
Eval-harness math — no database, no network, no API keys required.
"""

import pytest

from evals.in_terms_eval import cohens_kappa, format_violations


def make_output(headline="h" * 80, summary="s" * 200, key_points=None):
    return {"headline": headline, "summary": summary, "key_points": key_points or ["k" * 140] * 3}


def test_output_at_the_limits_passes_format_check():
    assert format_violations(make_output()) == []


def test_format_check_flags_each_overlong_field():
    problems = format_violations(
        make_output(headline="h" * 81, summary="s" * 201, key_points=["k" * 141, "ok", "ok"])
    )
    assert problems == ["headline 81>80", "summary 201>200", "key point 1 141>140"]


def test_format_check_flags_wrong_number_of_key_points():
    assert format_violations(make_output(key_points=["a", "b"])) == ["2 key points (want 3)"]


def test_perfect_agreement_is_kappa_one():
    assert cohens_kappa([(True, True), (False, False), (True, True)]) == pytest.approx(1.0)


def test_chance_level_agreement_is_kappa_zero():
    # Judge says yes half the time regardless of the human: 50% raw
    # agreement, but no better than coin-flipping.
    pairs = [(True, True), (True, False), (False, True), (False, False)]
    assert cohens_kappa(pairs) == pytest.approx(0.0)


def test_kappa_penalizes_a_judge_that_always_says_yes():
    # 9/10 raw agreement looks great, but the judge never says "no", so it
    # can't catch the one failure — kappa exposes that.
    pairs = [(True, True)] * 9 + [(False, True)]
    assert cohens_kappa(pairs) == pytest.approx(0.0)


def test_kappa_matches_hand_computed_value():
    # observed = 0.8; human_yes = 0.6, judge_yes = 0.6
    # expected = 0.36 + 0.16 = 0.52; kappa = (0.8 - 0.52) / 0.48
    pairs = [(True, True)] * 5 + [(False, False)] * 3 + [(True, False), (False, True)]
    assert cohens_kappa(pairs) == pytest.approx(0.28 / 0.48)


def test_kappa_undefined_when_empty_or_no_variation():
    assert cohens_kappa([]) is None
    assert cohens_kappa([(True, True), (True, True)]) is None


# --- compare_eval: the A/B significance test ---------------------------------

from evals.compare_eval import sign_test


def test_sign_test_matches_known_binomial_value():
    # 15 wins vs 5 losses: two-sided exact p = 0.0414.
    assert sign_test(15, 5) == pytest.approx(0.0414, abs=1e-4)


def test_sign_test_is_symmetric_and_one_when_even():
    assert sign_test(5, 15) == sign_test(15, 5)
    assert sign_test(4, 4) == 1.0


def test_sign_test_with_no_decisive_pairs_is_undefined():
    assert sign_test(0, 0) is None
