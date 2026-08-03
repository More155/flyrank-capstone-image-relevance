"""Seeds the `images` table from corpus.py. Idempotent on sha256 — running
this twice does not create duplicate rows.

Ground-truth subject labels live only in corpus.py, not in the DB: `images`
has no subject column on purpose. The vision model (jobs/classify.py) has
to earn its tags for real; the eval script (Step 5) cross-references
corpus.py by source_uri to check the model's answer against the label.
"""

from __future__ import annotations

import hashlib
import logging

from corpus import CORPUS
from db import get_connection
from jobs.classify import load_image_bytes

logger = logging.getLogger(__name__)


def seed() -> dict[str, int]:
    counts = {"inserted": 0, "skipped": 0, "failed": 0}
    with get_connection() as conn:
        for item in CORPUS:
            try:
                image_bytes, _mime_type = load_image_bytes(item.url)
            except OSError as exc:
                logger.warning("could not fetch %s (%s): %s", item.unsplash_id, item.subject.value, exc)
                counts["failed"] += 1
                continue

            sha256 = hashlib.sha256(image_bytes).hexdigest()
            with conn.cursor() as cur:
                cur.execute("select 1 from images where sha256 = %s", (sha256,))
                if cur.fetchone():
                    counts["skipped"] += 1
                    continue
                cur.execute(
                    "insert into images (source_uri, sha256) values (%s, %s)",
                    (item.url, sha256),
                )
                counts["inserted"] += 1
            conn.commit()

    logger.info("seed_corpus: %s", counts)
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(seed())
