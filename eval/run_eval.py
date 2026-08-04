"""Top-1 precision eval (source brief §12 Probe 5, glossary definition:
"Of all posts, the share whose first suggested image was the labeled
correct one.").

"Correct" here means the guard's top-suggested image's species matches
the post's hand-labeled expected species (posts_seed.SeedPost.expected_
subject) — not the model's own extracted posts.subject, which would be
grading the model against its own answer.

Posts with no real corpus coverage (expected_subject=UNKNOWN — the
elephant post) have no correct image to measure against, so they're
excluded from the precision denominator and reported separately as a
guard-behavior check instead (does it correctly refuse rather than guess).
"""

from __future__ import annotations

import asyncio

from db import get_connection
from matching import match_images_for_post
from posts_seed import POSTS
from schemas import Verdict
from vocab import Subject


async def run_eval() -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select id, title from posts")
            title_to_id = {title: post_id for post_id, title in cur.fetchall()}

    scored: list[tuple[str, str, str | None, bool]] = []
    no_coverage_checks: list[tuple[str, bool]] = []

    for post in POSTS:
        post_id = title_to_id.get(post.title)
        if post_id is None:
            raise SystemExit(f"post {post.title!r} not seeded — run scripts/seed_posts.py first")

        decision = await match_images_for_post(post_id)

        if post.expected_subject is Subject.UNKNOWN:
            no_coverage_checks.append((post.title, decision.verdict == Verdict.NO_MATCH))
            continue

        top_subject = None
        if decision.image_id is not None:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("select subject from image_tags where image_id = %s", (str(decision.image_id),))
                    row = cur.fetchone()
                    top_subject = row[0] if row else None

        correct = top_subject == post.expected_subject.value
        scored.append((post.title, post.expected_subject.value, top_subject, correct))

    precision = sum(c for *_, c in scored) / len(scored) if scored else 0.0

    return {
        "precision": precision,
        "correct": sum(c for *_, c in scored),
        "total": len(scored),
        "scored": scored,
        "no_coverage_checks": no_coverage_checks,
    }


def _print_report(result: dict) -> None:
    print(f"Top-1 precision: {result['precision']:.1%} ({result['correct']}/{result['total']})")
    print()
    for title, expected, got, correct in result["scored"]:
        mark = "PASS" if correct else "FAIL"
        print(f"  {mark}  {title!r}: expected={expected} got={got}")
    print()
    for title, ok in result["no_coverage_checks"]:
        mark = "PASS" if ok else "FAIL"
        note = "correctly refused (no_match)" if ok else "did NOT refuse — should have"
        print(f"  {mark}  {title!r} (no corpus coverage): {note}")


if __name__ == "__main__":
    result = asyncio.run(run_eval())
    _print_report(result)
