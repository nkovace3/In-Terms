"""
In Terms gates — no database, no network, no API keys required.

The feed is public and the endpoint is unauthenticated, so the daily cap is
the only thing bounding generation spend, and the sensitive check is the
only thing stopping e.g. a rape conviction being framed as a "playoff blowout".
"""

from types import SimpleNamespace

import pytest

from services import in_terms

CACHED = SimpleNamespace(headline="cached")


@pytest.fixture
def fake_in_terms(monkeypatch):
    """
    Replaces the DB and LLM steps. Knobs: `cached` (what the cache returns),
    `generated_today` (count toward the cap), `limit`; `generated` records
    calls that reached the model.
    """
    state = {
        "cached": None, "generated_today": 0, "limit": 3, "generated": [], "sensitive": False,
        "reference": None, "saved_reference_id": None,
    }

    async def fake_get_in_terms(db, article_id, target_category):
        return state["cached"]

    async def fake_get_article(db, article_id):
        return SimpleNamespace(id=article_id, category="NBA", sensitive=state["sensitive"])

    async def fake_count(db, since):
        return state["generated_today"]

    async def fake_generate(db, article, target_category):
        state["generated"].append((article.id, target_category))
        return in_terms.InTermsGeneration(result="result", reference=state["reference"], candidates=[])

    async def fake_save(db, article_id, target_category, result, reference_article_id=None):
        state["saved_reference_id"] = reference_article_id
        return result

    class FakeSettings:
        max_in_terms_generations_per_day = state["limit"]

        def pricing(self):
            return None

    monkeypatch.setattr(in_terms, "get_in_terms", fake_get_in_terms)
    monkeypatch.setattr(in_terms, "get_article", fake_get_article)
    monkeypatch.setattr(in_terms, "count_in_terms_since", fake_count)
    monkeypatch.setattr(in_terms, "generate_in_terms_for_article", fake_generate)
    monkeypatch.setattr(in_terms, "save_in_terms", fake_save)
    monkeypatch.setattr(in_terms, "get_settings", lambda: FakeSettings())
    return state


async def test_generates_under_the_cap(fake_in_terms):
    fake_in_terms["generated_today"] = 2

    result = await in_terms.get_or_generate_in_terms(None, 1, "Reality TV")

    assert result == "result"
    assert fake_in_terms["generated"] == [(1, "Reality TV")]


async def test_refuses_new_generation_at_the_cap(fake_in_terms):
    fake_in_terms["generated_today"] = 3

    with pytest.raises(in_terms.DailyLimitReached):
        await in_terms.get_or_generate_in_terms(None, 1, "Reality TV")

    # The point of the cap: the model is never called.
    assert fake_in_terms["generated"] == []


async def test_cached_result_is_served_even_past_the_cap(fake_in_terms):
    fake_in_terms["generated_today"] = 999
    fake_in_terms["cached"] = CACHED

    assert await in_terms.get_or_generate_in_terms(None, 1, "Reality TV") is CACHED


# None = saved before classification existed and not yet backfilled.
@pytest.mark.parametrize("sensitive", [True, None])
async def test_sensitive_or_unclassified_story_is_refused(fake_in_terms, sensitive):
    fake_in_terms["sensitive"] = sensitive

    with pytest.raises(in_terms.SensitiveStory):
        await in_terms.get_or_generate_in_terms(None, 1, "NFL")

    assert fake_in_terms["generated"] == []


async def test_cached_translation_of_sensitive_story_is_not_served(fake_in_terms):
    # Translations generated before the check existed are already cached.
    fake_in_terms["sensitive"] = True
    fake_in_terms["cached"] = CACHED

    with pytest.raises(in_terms.SensitiveStory):
        await in_terms.get_or_generate_in_terms(None, 1, "NFL")


async def test_chosen_parallel_is_saved_with_the_translation(fake_in_terms):
    fake_in_terms["reference"] = SimpleNamespace(id=42)

    await in_terms.get_or_generate_in_terms(None, 1, "Reality TV")

    assert fake_in_terms["saved_reference_id"] == 42


# --- resolve_reference: the model answers with a candidate *number* ----------

CANDIDATES = [SimpleNamespace(id=10), SimpleNamespace(id=20), SimpleNamespace(id=30)]


@pytest.mark.parametrize("number, expected_id", [(1, 10), (3, 30)])
def test_reference_number_is_one_based(number, expected_id):
    assert in_terms.resolve_reference(number, CANDIDATES, article_id=1).id == expected_id


# None = the model found no genuine parallel; 0/4 = it answered out of range,
# where showing no "Compared with" beats showing the wrong story.
@pytest.mark.parametrize("number", [None, 0, 4, -1])
def test_missing_or_out_of_range_reference_is_none(number):
    assert in_terms.resolve_reference(number, CANDIDATES, article_id=1) is None
