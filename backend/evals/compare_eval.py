"""
A/B eval: the analogy generator (services/in_terms.py) against the frozen
pre-analogy generator (evals/baseline_in_terms.py), on the same seeded
sample of (article, target) pairs, generated at the same time against the
same database.

  1. generate  Run both generators on N pairs. Nothing is saved to the DB.
  2. judge     For each output, an absolute verdict (faithful? compares to a
               real parallel? does the parallel hold? just a vocabulary swap?),
               plus a blind head-to-head run in BOTH orders, since LLM judges
               favor whichever answer they read first. A pair only counts as a
               win if the judge picks the same output both times.
  3. label     You pick the better card, blind (order randomized per item).
               The judge was near chance against hand labels before (README,
               kappa ~0.1), so the human preference is the result that counts;
               the judge is a second opinion, and `report` says how often
               they agree.
  4. report    Win rates with exact sign-test p-values, paired criteria with
               exact McNemar p-values, and retrieval stats.

    uv run python -m evals.compare_eval generate --n 40 --out evals/data/ab.jsonl
    # held-out confirmation, after tuning a prompt on ab.jsonl:
    uv run python -m evals.compare_eval generate --n 40 --seed 1 --exclude-from evals/data/ab.jsonl --out evals/data/heldout.jsonl
    uv run python -m evals.compare_eval judge  evals/data/ab.jsonl
    uv run python -m evals.compare_eval label  evals/data/ab.jsonl
    uv run python -m evals.compare_eval report evals/data/ab.jsonl
"""

import argparse
import asyncio
import json
import random
from math import comb
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select, text

from api.routes.articles import CATEGORIES
from database import SessionLocal
from evals.baseline_in_terms import generate_baseline
from evals.in_terms_eval import DEFAULT_JUDGE_MODEL, current_commit, format_violations, print_story, read_items, story_dict, write_items
from logging_config import configure_logging
from models import Article
from services.google import execute_query
from services.in_terms import generate_in_terms_for_article

VARIANTS = ("baseline", "analogy")
CRITERIA = ("faithful", "real_parallel", "parallel_holds", "vocabulary_swap")
# For vocabulary_swap, lower is better.
LOWER_IS_BETTER = {"vocabulary_swap"}
CONCURRENCY = 4


def card(output: dict) -> dict:
    return {k: output[k] for k in ("headline", "summary", "key_points")}


def reference_dict(article: Article) -> dict:
    return {"id": article.id, **story_dict(article)}


# --- generate -----------------------------------------------------------------


async def generate(out: Path, n: int, seed: int, exclude_from: list[Path]) -> None:
    if out.exists():
        raise SystemExit(f"{out} already exists — pick a new --out path.")

    db = SessionLocal()
    try:
        # Same pool the app can translate: classified non-sensitive articles.
        articles = db.scalars(select(Article).from_statement(text(
            "SELECT * FROM articles WHERE embedding IS NOT NULL AND dynamics IS NOT NULL "
            "AND sensitive IS FALSE ORDER BY published_at DESC LIMIT 200"
        ))).all()
        # Held-out runs exclude the articles a prompt was tuned on, so the
        # confirming result isn't measured on the data used to pick it.
        excluded = {item["article_id"] for path in exclude_from for item in read_items(path)}
        articles = [a for a in articles if a.id not in excluded]
        rng = random.Random(seed)
        targets = list(CATEGORIES.values())
        pairs = [
            (article, rng.choice([t for t in targets if t != article.category]))
            for article in rng.sample(list(articles), min(n, len(articles)))
        ]

        # Sequential: both generators share one DB session. ~80 model calls.
        results = []
        for i, (article, target) in enumerate(pairs, 1):
            print(f"[{i}/{len(pairs)}] {article.category} -> {target}: {article.headline[:60]}")
            try:
                baseline_output, baseline_ref = await generate_baseline(db, article, target)
                generation = await generate_in_terms_for_article(db, article, target)
            except Exception as e:
                print(f"  FAILED: {e}")
                continue
            chosen = generation.reference
            results.append({
                "id": f"{article.id}->{target}",
                "article_id": article.id,
                "source_category": article.category,
                "target_category": target,
                "source": story_dict(article),
                "variants": {
                    "baseline": {"output": baseline_output, "reference": baseline_ref},
                    "analogy": {
                        "output": card({k: getattr(generation.result, k) for k in ("headline", "summary", "key_points")}),
                        "reference": reference_dict(chosen) if chosen else None,
                        "why_it_matches": generation.result.why_it_matches,
                        "candidates": [reference_dict(c) for c in generation.candidates],
                        # 1-based rank of the pick by embedding distance, so
                        # report can show whether choosing beat taking top-1.
                        "chosen_rank": next((r for r, c in enumerate(generation.candidates, 1) if chosen and c.id == chosen.id), None),
                    },
                },
                # Fixed per item so labeling is blind but reproducible.
                "blind_order": rng.sample(VARIANTS, 2),
                "human": {"preference": None, "notes": ""},
            })
    finally:
        db.close()

    items = results
    for item in items:
        item["commit"] = current_commit()
    write_items(out, items)
    print(f"Wrote {len(items)} items to {out} ({len(pairs) - len(items)} failed)")


# --- judge --------------------------------------------------------------------


class OutputVerdict(BaseModel):
    # Evidence before verdicts, as in in_terms_eval.JudgeVerdict.
    unsupported_claims: list[str] = Field(
        description="Every claim in the CARD not supported by the ORIGINAL STORY or the REFERENCE STORY, including facts moved from one story onto the other, and real entities relabeled into fictional roles. Empty if none."
    )
    faithful: bool = Field(description="True only if unsupported_claims is empty.")
    named_parallel: str = Field(
        description="The specific real event the CARD explicitly compares the original story to, quoted or paraphrased. Empty if it names none (a generic trope like 'a villain edit' is not a specific event)."
    )
    real_parallel: bool = Field(description="True only if named_parallel is non-empty.")
    parallel_holds: bool = Field(
        description="True only if real_parallel and the two situations genuinely share structure (the same kind of move, similar roles and stakes), not just a topic word or a vague mood."
    )
    vocabulary_swap: bool = Field(
        description="True if the CARD is mostly the original story restated with target-domain words swapped in, adding no understanding of the original."
    )
    reasoning: str = Field(description="One or two sentences.")


def output_prompt(item: dict, variant: str) -> str:
    v = item["variants"][variant]
    reference = json.dumps(card(v["reference"]), indent=2, ensure_ascii=False) if v["reference"] else "None."
    return f"""
You are grading a news card that explains a real story to someone who
follows {item["target_category"]}.

ORIGINAL STORY (ground truth):
{json.dumps(item["source"], indent=2, ensure_ascii=False)}

REFERENCE STORY (a real {item["target_category"]} story the writer was shown;
facts about it are allowed only if attributed to it):
{reference}

CARD TO GRADE:
{json.dumps(card(v["output"]), indent=2, ensure_ascii=False)}

Grade each field as described in the schema. Be strict and grade what is
written, not what was intended. An explicit comparison ("like", "mirrors")
is framing, not a claim; attributing one story's facts to the other is a
claim, and is unsupported.
"""


class PairwiseVerdict(BaseModel):
    reasoning: str = Field(description="Two or three sentences comparing the cards.")
    winner: Literal["A", "B", "tie"]


def pairwise_prompt(item: dict, first: str, second: str) -> str:
    def block(label: str, variant: str) -> str:
        v = item["variants"][variant]
        ref = json.dumps(card(v["reference"]), ensure_ascii=False) if v["reference"] else "None."
        return (f"CARD {label}:\n{json.dumps(card(v['output']), indent=2, ensure_ascii=False)}\n"
                f"Reference story shown to card {label}'s writer: {ref}")

    return f"""
Two cards explain the same real news story to someone who follows
{item["target_category"]}.

ORIGINAL STORY (ground truth):
{json.dumps(item["source"], indent=2, ensure_ascii=False)}

{block("A", first)}

{block("B", second)}

Which card would leave a {item["target_category"]} fan understanding the
original story better, through a genuine, insightful comparison to something
real rather than vocabulary swapped into the same story? Any invented or
misattributed fact is a serious flaw. Don't prefer a card for being longer or
more dramatic. Say "tie" only if they are genuinely equal.
"""


async def judge(path: Path, model: str) -> None:
    items = read_items(path)
    out = judge_path(path, model)
    done = {v["id"] for v in read_items(out)} if out.exists() else set()
    todo = [item for item in items if item["id"] not in done]
    print(f"Judging {len(todo)} items with {model} ({len(done)} already done)")
    semaphore = asyncio.Semaphore(CONCURRENCY)
    write_lock = asyncio.Lock()

    async def ask(prompt: str, schema):
        async with semaphore:
            response = await execute_query(prompt, schema, model=model)
        return schema.model_validate_json(response.text)

    async def run(item: dict) -> None:
        try:
            verdicts = await asyncio.gather(
                *(ask(output_prompt(item, v), OutputVerdict) for v in VARIANTS),
                ask(pairwise_prompt(item, "baseline", "analogy"), PairwiseVerdict),
                ask(pairwise_prompt(item, "analogy", "baseline"), PairwiseVerdict),
            )
        except Exception as e:
            # One bad response shouldn't sink the whole run; rerunning
            # `judge` picks up whatever was skipped.
            print(f"{item['id']}: FAILED ({e}); rerun judge to retry")
            return
        baseline_v, analogy_v, ab, ba = verdicts
        orders = [
            {"A": "baseline", "B": "analogy"}.get(ab.winner, "tie"),
            {"A": "analogy", "B": "baseline"}.get(ba.winner, "tie"),
        ]
        record = {
            "id": item["id"],
            "model": model,
            "outputs": {"baseline": baseline_v.model_dump(), "analogy": analogy_v.model_dump()},
            "pairwise_orders": orders,
            "pairwise_reasoning": [ab.reasoning, ba.reasoning],
            # Order-consistent winner, else tie.
            "preference": orders[0] if orders[0] == orders[1] else "tie",
        }
        async with write_lock:
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"{item['id']}: preference={record['preference']} (orders: {orders})")

    await asyncio.gather(*(run(item) for item in todo))
    print(f"Verdicts in {out}")


def judge_path(items_path: Path, model: str) -> Path:
    return items_path.with_name(f"{items_path.stem}.judge.{model}.jsonl")


# --- label --------------------------------------------------------------------


def label(path: Path) -> None:
    items = read_items(path)
    todo = [item for item in items if item["human"]["preference"] is None]
    print(f"{len(items) - len(todo)}/{len(items)} already labeled.")
    print("\nPick the card that would leave a fan of the target domain understanding the\n"
          "original story better. Invented or misattributed facts count heavily against.\n"
          "You won't be told which generator wrote which card.")
    try:
        for n, item in enumerate(todo, 1):
            print(f"\n{'=' * 78}\n[{n}/{len(todo)}] {item['source_category']} -> {item['target_category']}")
            print_story("ORIGINAL", item["source"])
            for letter, variant in zip("AB", item["blind_order"]):
                v = item["variants"][variant]
                print_story(f"CARD {letter}", card(v["output"]))
                if v["reference"]:
                    print(f"    (writer was shown: {v['reference']['headline']})")
            print()
            while True:
                answer = input("  Better card? [a/b/t=tie, s=skip, q=quit] ").strip().lower()
                if answer in ("a", "b", "t", "s", "q"):
                    break
            if answer == "q":
                raise KeyboardInterrupt
            if answer == "s":
                continue
            item["human"]["preference"] = "tie" if answer == "t" else item["blind_order"]["ab".index(answer)]
            note = input("  notes (optional): ").strip()
            if note:
                item["human"]["notes"] = note
            write_items(path, items)
    except (KeyboardInterrupt, EOFError):
        print("\nStopped — progress saved.")


# --- report -------------------------------------------------------------------


def sign_test(wins: int, losses: int) -> float | None:
    """
    Exact two-sided binomial test that wins and losses are equally likely
    (ties dropped). Also serves as the exact McNemar test when given the two
    kinds of discordant pairs.
    """
    n = wins + losses
    if n == 0:
        return None
    k = min(wins, losses)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def preference_line(label: str, prefs: list[str]) -> str:
    a, b, t = prefs.count("analogy"), prefs.count("baseline"), prefs.count("tie")
    p = sign_test(a, b)
    return (f"  {label:<22} analogy {a:>3}   baseline {b:>3}   tie {t:>3}   "
            f"p={'—' if p is None else f'{p:.3g}'}  (n={len(prefs)})")


def report(path: Path, model: str) -> None:
    items = {item["id"]: item for item in read_items(path)}
    verdicts_file = judge_path(path, model)
    verdicts = {v["id"]: v for v in read_items(verdicts_file)} if verdicts_file.exists() else {}
    print(f"{path}: {len(items)} items, {len(verdicts)} judged by {model}\n")

    print("Head-to-head (p = exact sign test, ties dropped; p < 0.05 = unlikely to be chance)")
    human = {i: item["human"]["preference"] for i, item in items.items() if item["human"]["preference"]}
    print(preference_line("you (blind)", list(human.values())))
    print(preference_line("judge (order-consistent)", [v["preference"] for v in verdicts.values()]))
    inconsistent = sum(v["pairwise_orders"][0] != v["pairwise_orders"][1] for v in verdicts.values())
    print(f"  judge flipped its pick when the order was swapped on {inconsistent}/{len(verdicts)} items")
    both = [i for i in human if i in verdicts]
    if both:
        agree = sum(human[i] == verdicts[i]["preference"] for i in both)
        print(f"  you and the judge agree on {agree}/{len(both)} items")

    if verdicts:
        print(f"\nPer-output judge criteria (paired; p = exact McNemar)")
        print(f"  {'criterion':<17}{'baseline':>10}{'analogy':>10}{'p':>9}")
        for criterion in CRITERIA:
            pairs = [(v["outputs"]["baseline"][criterion], v["outputs"]["analogy"][criterion]) for v in verdicts.values()]
            only_analogy = sum(a and not b for b, a in pairs)
            only_baseline = sum(b and not a for b, a in pairs)
            p = sign_test(only_analogy, only_baseline)
            note = "  (lower is better)" if criterion in LOWER_IS_BETTER else ""
            print(f"  {criterion:<17}{pct(sum(b for b, _ in pairs), len(pairs)):>10}"
                  f"{pct(sum(a for _, a in pairs), len(pairs)):>10}"
                  f"{('—' if p is None else f'{p:.3g}'):>9}{note}")

    print("\nFormat (code-checked, current limits)")
    for variant in VARIANTS:
        ok = sum(not format_violations(item["variants"][variant]["output"]) for item in items.values())
        print(f"  {variant:<10}{pct(ok, len(items))} within limits")

    analogy = [item["variants"]["analogy"] for item in items.values()]
    ranks = [a["chosen_rank"] for a in analogy]
    print("\nRetrieval (analogy)")
    print(f"  chose a parallel: {pct(sum(r is not None for r in ranks), len(ranks))}  "
          f"(abstained {sum(r is None for r in ranks)})")
    print(f"  picked something other than the nearest neighbor: "
          f"{sum(r not in (None, 1) for r in ranks)}/{sum(r is not None for r in ranks)}  "
          f"ranks: {sorted(r for r in ranks if r is not None)}")
    print(f"  avg candidates offered: {sum(len(a['candidates']) for a in analogy) / max(len(analogy), 1):.1f}")

    if verdicts:
        by_target: dict[str, list[str]] = {}
        for i, v in verdicts.items():
            by_target.setdefault(items[i]["target_category"], []).append(v["preference"])
        print("\nJudge head-to-head by target category")
        for target, prefs in sorted(by_target.items()):
            print(preference_line(target, prefs))

        losses = [i for i, v in verdicts.items() if v["preference"] == "baseline"]
        if losses:
            # Reading these is the point: each is either a prompt problem or
            # a judge problem.
            print(f"\nItems where the judge preferred the baseline ({len(losses)}):")
            for i in losses:
                print(f"  {i}: {verdicts[i]['pairwise_reasoning'][0]}")


def pct(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.0%}" if denominator else "—"


# --- cli ----------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="A/B the In Terms generator against the frozen baseline.")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("generate")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--exclude-from", type=Path, nargs="*", default=[],
                   help="Skip articles that appear in these item files (e.g. the dev set).")

    p = commands.add_parser("label")
    p.add_argument("path", type=Path)

    for name in ("judge", "report"):
        p = commands.add_parser(name)
        p.add_argument("path", type=Path)
        p.add_argument("--model", default=DEFAULT_JUDGE_MODEL)

    args = parser.parse_args()
    configure_logging()

    if args.command == "generate":
        asyncio.run(generate(args.out, args.n, args.seed, args.exclude_from))
    elif args.command == "judge":
        asyncio.run(judge(args.path, args.model))
    elif args.command == "label":
        label(args.path)
    else:
        report(args.path, args.model)


if __name__ == "__main__":
    main()
