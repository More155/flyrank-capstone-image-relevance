"""Live verification of Step 4's "done when" criteria — the same checks
as the source brief's acceptance probes 2-4. Requires posts_seed.py and
corpus.py to already be seeded (scripts/seed_corpus.py, jobs/classify.py,
jobs/embed_images.py, scripts/seed_posts.py).

Not a pytest suite on purpose: this hits the live DB and Gemini API, which
the rest of the test suite deliberately never does.
"""

from __future__ import annotations

import asyncio

from db import get_connection
from guard import guard
from matching import match_images_for_post, rank_images_for_post
from schemas import GuardReason, Verdict
from vocab import Subject


def _get_post_id(cur, title: str):
    cur.execute("select id from posts where title = %s", (title,))
    row = cur.fetchone()
    if row is None:
        raise SystemExit(f"post {title!r} not seeded — run scripts/seed_posts.py first")
    return row[0]


async def main() -> None:
    checks: list[tuple[str, bool]] = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            fox_post_id = _get_post_id(cur, "Getting to Know the Red Fox")
            vulpes_post_id = _get_post_id(cur, "The Secretive World of Vulpes Vulpes")
            elephant_post_id = _get_post_id(cur, "The Majestic African Elephant")

    # Probe 2: fox post ranks a real fox image top.
    decision = await match_images_for_post(fox_post_id)
    top = rank_images_for_post(fox_post_id, top_k=1)[0]
    ok = decision.verdict == Verdict.SUGGEST and top.subject == Subject.RED_FOX
    checks.append(("fox post ranks fox top and suggests it", ok))

    # Probe 3: force a real wolf candidate onto the fox post -> rejected.
    candidates = rank_images_for_post(fox_post_id, top_k=48)
    wolf_only = [c for c in candidates if c.subject == Subject.GRAY_WOLF][:1]
    forced = guard(Subject.RED_FOX, wolf_only, sim_floor=0.35, conf_floor=0.6)
    ok = forced.verdict == Verdict.NO_MATCH and forced.reason == GuardReason.SUBJECT_MISMATCH
    checks.append(("forced wolf candidate on fox post is rejected with a reason", ok))

    # Paraphrase: "Vulpes vulpes" post (no literal "fox") still matches fox.
    decision = await match_images_for_post(vulpes_post_id)
    ok = decision.verdict == Verdict.SUGGEST
    checks.append(('"Vulpes vulpes" paraphrase post still matches fox', ok))

    # Probe 4: a post with no corpus coverage (elephant) gets no confident match.
    decision = await match_images_for_post(elephant_post_id)
    ok = decision.verdict == Verdict.NO_MATCH
    checks.append(("post with no good image gets no_match, not a guess", ok))

    print()
    all_ok = True
    for label, ok in checks:
        print(("PASS" if ok else "FAIL"), "-", label)
        all_ok = all_ok and ok
    print()
    if not all_ok:
        raise SystemExit(1)
    print("all Step 4 checks passed")


if __name__ == "__main__":
    asyncio.run(main())
