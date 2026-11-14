"""
Evaluate In Terms output against the two things the prompt promises:

  faithful         — every fact, name, and entity matches the source story;
                     nothing invented, changed, or relabeled ("cast",
                     "episode") into a fictional version.
  domain_specific  — uses at least one *named*, recognizable trope of the
                     target domain as a comparison, not just generic
                     intensity words ("drama", "crisis", "setback").

Workflow (run from backend/):

  1. export   Write items to label: cached In Terms rows (free), or --fresh
              ones generated now with the current prompt (costs API calls).
  2. label    Interactively record your own verdicts. Resumable.
  3. judge    Have an LLM grade the same items on the same two criteria.
  4. report   Pass rates, plus how often the judge agrees with you.

The judge is only worth trusting once `report` shows it agrees with your
labels. After that, re-running export --fresh + judge is a cheap regression
check for any prompt change.

    uv run python -m evals.in_terms_eval export --out evals/data/cached.jsonl
    uv run python -m evals.in_terms_eval label  evals/data/cached.jsonl
    uv run python -m evals.in_terms_eval judge  evals/data/cached.jsonl
    uv run python -m evals.in_terms_eval report evals/data/cached.jsonl
"""

import argparse
import asyncio
import json
import random
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import select, text

from api.routes.articles import CATEGORIES
from database import SessionLocal
from logging_config import configure_logging
from models import Article, InTerms
from services.google import execute_query
from services.in_terms import generate_in_terms_for_article

CRITERIA = ("faithful", "domain_specific")

# Pinned (not "gemini-flash-latest") so verdicts stay comparable over time,
# and deliberately stronger than the generator (gemini-3.5-flash-lite) — a
# model grading its own output tends to go easy on it.
DEFAULT_JUDGE_MODEL = "gemini-3.8-flash"


# --- file helpers -------------------------------------------------------------


def read_items(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_items(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def judge_path(items_path: Path, model: str) -> Path:
    # Verdicts live next to the items, one file per judge model, so
    # re-judging with another model never overwrites your human labels.
    return items_path.with_name(f"{items_path.stem}.judge.{model}.jsonl")


def story_dict(row) -> dict:
    return {"headline": row.headline, "summary": row.summary, "key_points": row.key_points}


def current_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def make_item(article: Article, target: str, output: dict, origin: str) -> dict:
    return {
        "id": f"{article.id}->{target}",
        "article_id": article.id,
        "source_category": article.category,
        "target_category": target,
        "origin": origin,
        "source": story_dict(article),
        "output": output,
        "human": {"faithful": None, "domain_specific": None, "notes": ""},
    }


# --- export -------------------------------------------------------------------


async def export(out: Path, fresh: int, seed: int) -> None:
    db = SessionLocal()
    try:
        if fresh:
            items = await export_fresh(db, fresh, seed)
        else:
            items = export_cached(db)
    finally:
        db.close()

    if out.exists():
        # Never clobber a file that may already hold hours of labels.
        raise SystemExit(f"{out} already exists — pick a new --out path.")
    write_items(out, items)
    print(f"Wrote {len(items)} items to {out}")


def export_cached(db) -> list[dict]:
    rows = db.scalars(
        select(InTerms).from_statement(text("SELECT * FROM in_terms ORDER BY id"))
    ).all()
    return [
        make_item(row.article, row.target_category, story_dict(row), origin="cached")
        for row in rows
    ]


async def export_fresh(db, count: int, seed: int) -> list[dict]:
    """
    Generate new In Terms with the *current* prompt for a random, seeded
    sample of (article, target) pairs. Nothing is saved to the database.
    """
    rng = random.Random(seed)
    articles = db.scalars(
        select(Article).from_statement(text(
            "SELECT * FROM articles WHERE embedding IS NOT NULL "
            "AND dynamics IS NOT NULL ORDER BY published_at DESC LIMIT 200"
        ))
    ).all()
    targets = list(CATEGORIES.values())
    pairs = []
    for article in rng.sample(list(articles), min(count, len(articles))):
        pairs.append((article, rng.choice([t for t in targets if t != article.category])))

    origin = f"fresh@{current_commit() or 'unknown'}"
    items = []
    for i, (article, target) in enumerate(pairs, 1):
        print(f"[{i}/{len(pairs)}] {article.category} -> {target}: {article.headline}")
        generation = await generate_in_terms_for_article(db, article, target)
        output = {k: getattr(generation.result, k) for k in ("headline", "summary", "key_points")}
        items.append(make_item(article, target, output, origin))
    return items


# --- label --------------------------------------------------------------------


def print_story(title: str, story: dict) -> None:
    print(f"\n  {title}")
    print(f"    Headline: {story['headline']}")
    print(f"    Summary:  {story['summary']}")
    for point in story["key_points"]:
        print(f"      - {point}")


def ask_bool(question: str) -> bool | None:
    while True:
        answer = input(f"  {question} [y/n, s=skip, q=quit] ").strip().lower()
        if answer in ("y", "n"):
            return answer == "y"
        if answer == "s":
            return None
        if answer == "q":
            raise KeyboardInterrupt


def label(path: Path) -> None:
    items = read_items(path)
    todo = [item for item in items if any(item["human"][c] is None for c in CRITERIA)]
    print(f"{len(items) - len(todo)}/{len(items)} already labeled.")

    print(
        "\nfaithful:        every fact/name/entity matches the source; nothing invented,\n"
        "                 changed, or relabeled into a fictional version.\n"
        "domain_specific: names at least one recognizable trope of the target domain\n"
        "                 as a comparison — not just generic words like 'drama'."
    )

    try:
        for n, item in enumerate(todo, 1):
            print(f"\n{'=' * 78}\n[{n}/{len(todo)}] {item['id']}  "
                  f"({item['source_category']} -> {item['target_category']})")
            print_story("SOURCE", item["source"])
            print_story(f"IN TERMS OF {item['target_category'].upper()}", item["output"])
            print()
            for criterion in CRITERIA:
                if item["human"][criterion] is None:
                    item["human"][criterion] = ask_bool(f"{criterion}?")
            note = input("  notes (optional): ").strip()
            if note:
                item["human"]["notes"] = note
            # Save after every item so quitting midway loses nothing.
            write_items(path, items)
    except (KeyboardInterrupt, EOFError):
        print("\nStopped — progress saved.")


# --- judge --------------------------------------------------------------------


class JudgeVerdict(BaseModel):
    # Evidence fields come before the verdicts on purpose: making the model
    # list specifics first tends to give more reliable yes/no calls than
    # asking for the verdict up front.
    invented_or_changed_claims: list[str] = Field(
        description="Every claim, name, or detail in the OUTPUT that is not supported by, or contradicts, the SOURCE. Include entities relabeled into fictional roles. Empty if none."
    )
    faithful: bool = Field(description="True only if invented_or_changed_claims is empty.")
    target_domain_tropes: list[str] = Field(
        description="Specific, named tropes/conventions of the target domain the OUTPUT uses as a comparison. Generic intensity words (drama, crisis, setback, twist) do not count. Empty if none."
    )
    domain_specific: bool = Field(description="True only if at least one specific trope is listed.")
    reasoning: str = Field(description="One or two sentences.")


def judge_prompt(item: dict) -> str:
    return f"""
You are grading a rewrite of a real news story "in terms of" another domain.
The rewrite must keep every real fact and only change tone and framing.

SOURCE STORY (ground truth):
{json.dumps(item["source"], indent=2, ensure_ascii=False)}

TARGET DOMAIN: {item["target_category"]}

OUTPUT TO GRADE:
{json.dumps(item["output"], indent=2, ensure_ascii=False)}

Grade two things independently.

1. FAITHFUL. Compare every claim in the OUTPUT against the SOURCE. List any
   claim, number, name, event, cause, or detail that the SOURCE does not
   support or that contradicts it. Also list real people or organizations
   relabeled as fictional {item["target_category"]} roles (e.g. calling a team a
   "cast" or a game an "episode"). An explicit comparison ("the kind of twist
   a reality show would build an episode around") is framing, not a claim,
   and is allowed. faithful is true only if your list is empty.

2. DOMAIN_SPECIFIC. List the specific, recognizable tropes or conventions of
   {item["target_category"]} that the OUTPUT actually uses. A trope must be
   something a {item["target_category"]} fan would recognize as belonging to that
   domain. Generic words that would fit any domain ("drama", "crisis",
   "setback", "twist", "high stakes") do not count. domain_specific is true
   only if your list has at least one entry.

Be strict. Do not give credit for intent — grade what is written.
"""


async def judge(path: Path, model: str) -> None:
    items = read_items(path)
    out = judge_path(path, model)
    done = {v["id"] for v in read_items(out)} if out.exists() else set()
    todo = [item for item in items if item["id"] not in done]
    print(f"Judging {len(todo)} items with {model} ({len(done)} already done)")

    for n, item in enumerate(todo, 1):
        response = await execute_query(judge_prompt(item), JudgeVerdict, model=model)
        verdict = JudgeVerdict.model_validate_json(response.text)
        # Append one line per item so an interrupted run resumes cleanly.
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": item["id"], "model": model, **verdict.model_dump()},
                               ensure_ascii=False) + "\n")
        print(f"[{n}/{len(todo)}] {item['id']}: "
              f"faithful={verdict.faithful} domain_specific={verdict.domain_specific}")

    print(f"Verdicts in {out}")


# --- report -------------------------------------------------------------------


def cohens_kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """
    Agreement beyond chance. Raw % agreement flatters a judge that just says
    "yes" to everything when most items pass; kappa corrects for that.
    ~0.6+ is usually read as substantial agreement, ~0.8+ as strong.
    """
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(h == j for h, j in pairs) / n
    human_yes = sum(h for h, _ in pairs) / n
    judge_yes = sum(j for _, j in pairs) / n
    expected = human_yes * judge_yes + (1 - human_yes) * (1 - judge_yes)
    if expected == 1:
        return None  # Both raters gave a single answer to everything.
    return (observed - expected) / (1 - expected)


# Reasonable ceilings for the card UI (InTermsResult's max_lengths), widened
# when cards became comparisons of two stories; accuracy beats brevity, so
# this flags outliers rather than setting a tight budget.
LIMITS = {"headline": 80, "summary": 200, "key_point": 140, "key_point_count": 3}


def format_violations(output: dict) -> list[str]:
    """
    Deterministic checks — no human or LLM needed for what code can verify
    exactly. These are the limits the prompt asks for and the card UI is
    designed around.
    """
    problems = []
    if len(output["headline"]) > LIMITS["headline"]:
        problems.append(f"headline {len(output['headline'])}>{LIMITS['headline']}")
    if len(output["summary"]) > LIMITS["summary"]:
        problems.append(f"summary {len(output['summary'])}>{LIMITS['summary']}")
    if len(output["key_points"]) != LIMITS["key_point_count"]:
        problems.append(f"{len(output['key_points'])} key points (want {LIMITS['key_point_count']})")
    for i, point in enumerate(output["key_points"], 1):
        if len(point) > LIMITS["key_point"]:
            problems.append(f"key point {i} {len(point)}>{LIMITS['key_point']}")
    return problems


def report(path: Path, model: str) -> None:
    items = {item["id"]: item for item in read_items(path)}
    verdicts_file = judge_path(path, model)
    verdicts = {v["id"]: v for v in read_items(verdicts_file)} if verdicts_file.exists() else {}

    print(f"{path}: {len(items)} items, {len(verdicts)} judged by {model}\n")

    violations = {item_id: format_violations(item["output"]) for item_id, item in items.items()}
    failing = [item_id for item_id, problems in violations.items() if problems]
    print(f"Format (code-checked): {pct(len(items) - len(failing), len(items))} within limits")
    for item_id in failing:
        print(f"  {item_id}: {', '.join(violations[item_id])}")
    print()
    print(f"{'criterion':<17}{'human pass':>12}{'judge pass':>12}{'agree':>9}{'kappa':>8}{'n':>5}")

    disagreements = []
    for criterion in CRITERIA:
        human = [i["human"][criterion] for i in items.values() if i["human"][criterion] is not None]
        judged = [v[criterion] for v in verdicts.values()]
        pairs = [
            (item["human"][criterion], verdicts[item_id][criterion])
            for item_id, item in items.items()
            if item["human"][criterion] is not None and item_id in verdicts
        ]
        kappa = cohens_kappa(pairs)

        print(
            f"{criterion:<17}"
            f"{pct(sum(human), len(human)):>12}"
            f"{pct(sum(judged), len(judged)):>12}"
            f"{pct(sum(h == j for h, j in pairs), len(pairs)):>9}"
            f"{(f'{kappa:.2f}' if kappa is not None else '—'):>8}"
            f"{len(pairs):>5}"
        )

        for item_id, item in items.items():
            h = item["human"][criterion]
            if h is not None and item_id in verdicts and verdicts[item_id][criterion] != h:
                disagreements.append((criterion, item_id, h, verdicts[item_id]))

    if verdicts:
        # Failures rarely spread evenly — knowing which target domains
        # break most tells you where prompt work will pay off.
        by_target: dict[str, list[dict]] = {}
        for item_id, verdict in verdicts.items():
            if item_id in items:
                by_target.setdefault(items[item_id]["target_category"], []).append(verdict)
        print(f"\nJudge pass rate by target category:")
        print(f"  {'target':<14}{'n':>4}{'faithful':>10}{'specific':>10}")
        for target, vs in sorted(by_target.items(), key=lambda kv: sum(v["faithful"] for v in kv[1]) / len(kv[1])):
            print(
                f"  {target:<14}{len(vs):>4}"
                f"{pct(sum(v['faithful'] for v in vs), len(vs)):>10}"
                f"{pct(sum(v['domain_specific'] for v in vs), len(vs)):>10}"
            )

    if disagreements:
        # Reading these is the point: each one is either a judge prompt bug
        # or a labeling call worth reconsidering.
        print(f"\nDisagreements ({len(disagreements)}):")
        for criterion, item_id, human_value, verdict in disagreements:
            evidence = verdict["invented_or_changed_claims" if criterion == "faithful" else "target_domain_tropes"]
            print(f"  {item_id} {criterion}: you={human_value} judge={verdict[criterion]}")
            print(f"    judge: {verdict['reasoning']}")
            if evidence:
                print(f"    cited: {evidence}")


def pct(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.0%}" if denominator else "—"


# --- cli ----------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate In Terms output quality.")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("export", help="Write items to label.")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--fresh", type=int, default=0, metavar="N",
                   help="Generate N new outputs with the current prompt instead of exporting cached ones.")
    p.add_argument("--seed", type=int, default=0)

    p = commands.add_parser("label", help="Label items interactively.")
    p.add_argument("path", type=Path)

    for name, help_text in (("judge", "Grade items with an LLM."), ("report", "Compare human and judge verdicts.")):
        p = commands.add_parser(name, help=help_text)
        p.add_argument("path", type=Path)
        p.add_argument("--model", default=DEFAULT_JUDGE_MODEL)

    args = parser.parse_args()
    configure_logging()

    if args.command == "export":
        asyncio.run(export(args.out, args.fresh, args.seed))
    elif args.command == "label":
        label(args.path)
    elif args.command == "judge":
        asyncio.run(judge(args.path, args.model))
    else:
        report(args.path, args.model)


if __name__ == "__main__":
    main()
