"""The ~50-image corpus — source of truth for both DB seeding
(`scripts/seed_corpus.py`) and, later, the eval ground truth
(`eval/run_eval.py`, Step 5).

Images are real Unsplash photos, verified reachable by URL (not committed
as binary files — `source_uri` points straight at Unsplash's CDN, so
re-running `scripts/seed_corpus.py` reproduces the same corpus on any
machine). Used under the Unsplash License: free for any use, no permission
or attribution required — https://unsplash.com/license.
"""

from __future__ import annotations

from dataclasses import dataclass

from vocab import Subject


@dataclass(frozen=True)
class CorpusImage:
    subject: Subject
    unsplash_id: str

    @property
    def url(self) -> str:
        return f"https://images.unsplash.com/photo-{self.unsplash_id}?auto=format&fit=crop&w=800&q=80"


CORPUS: list[CorpusImage] = [
    # red fox
    CorpusImage(Subject.RED_FOX, "1474511320723-9a56873867b5"),
    CorpusImage(Subject.RED_FOX, "1557008075-7f2c5efa4cfd"),
    CorpusImage(Subject.RED_FOX, "1619148189616-013b06952c04"),
    CorpusImage(Subject.RED_FOX, "1605101479435-005f9c563944"),
    CorpusImage(Subject.RED_FOX, "1621206593424-6e4e8f6336e9"),
    CorpusImage(Subject.RED_FOX, "1560809451-9e77c2e8214a"),
    CorpusImage(Subject.RED_FOX, "1516934024742-b461fba47600"),
    CorpusImage(Subject.RED_FOX, "1551725301-5183dc1dbb83"),
    # gray wolf
    CorpusImage(Subject.GRAY_WOLF, "1607350999170-b893fef057ea"),
    CorpusImage(Subject.GRAY_WOLF, "1583589261738-c7eac1b20537"),
    CorpusImage(Subject.GRAY_WOLF, "1552249007-6759fe2742b6"),
    CorpusImage(Subject.GRAY_WOLF, "1604608678051-64d46d8d0ffe"),
    CorpusImage(Subject.GRAY_WOLF, "1510853675132-58241c941e4f"),
    CorpusImage(Subject.GRAY_WOLF, "1572008125457-15e3be61ce3e"),
    CorpusImage(Subject.GRAY_WOLF, "1546638285-f17602bf4bdc"),
    CorpusImage(Subject.GRAY_WOLF, "1680201036424-37d5c5c812dd"),
    # domestic dog
    CorpusImage(Subject.DOMESTIC_DOG, "1530281700549-e82e7bf110d6"),
    CorpusImage(Subject.DOMESTIC_DOG, "1552053831-71594a27632d"),
    CorpusImage(Subject.DOMESTIC_DOG, "1561037404-61cd46aa615b"),
    CorpusImage(Subject.DOMESTIC_DOG, "1503256207526-0d5d80fa2f47"),
    CorpusImage(Subject.DOMESTIC_DOG, "1543466835-00a7907e9de1"),
    CorpusImage(Subject.DOMESTIC_DOG, "1518020382113-a7e8fc38eac9"),
    CorpusImage(Subject.DOMESTIC_DOG, "1504826260979-242151ee45b7"),
    CorpusImage(Subject.DOMESTIC_DOG, "1537151625747-768eb6cf92b2"),
    # red panda
    CorpusImage(Subject.RED_PANDA, "1656899367728-cf0194bf3aeb"),
    CorpusImage(Subject.RED_PANDA, "1542880941-1abfea46bba6"),
    CorpusImage(Subject.RED_PANDA, "1656899367682-4afdbbf07df6"),
    CorpusImage(Subject.RED_PANDA, "1656899367684-6f234eff00a7"),
    CorpusImage(Subject.RED_PANDA, "1463436755683-3f805a9d1192"),
    CorpusImage(Subject.RED_PANDA, "1538099130811-745e64318258"),
    CorpusImage(Subject.RED_PANDA, "1706859686032-8c4d4ddb6380"),
    CorpusImage(Subject.RED_PANDA, "1542880696-78ba55200f0f"),
    # raccoon
    CorpusImage(Subject.RACCOON, "1497752531616-c3afd9760a11"),
    CorpusImage(Subject.RACCOON, "1601247387431-7966d811f30b"),
    CorpusImage(Subject.RACCOON, "1601247387326-f8bcb5a234d4"),
    CorpusImage(Subject.RACCOON, "1615812214207-34e3be6812df"),
    CorpusImage(Subject.RACCOON, "1691874135454-c063836f70dd"),
    CorpusImage(Subject.RACCOON, "1586466954038-0d406cb6adfe"),
    CorpusImage(Subject.RACCOON, "1682627101090-323012f3b832"),
    CorpusImage(Subject.RACCOON, "1577936558471-8b80b49b0117"),
    # domestic cat
    CorpusImage(Subject.DOMESTIC_CAT, "1495360010541-f48722b34f7d"),
    CorpusImage(Subject.DOMESTIC_CAT, "1503777119540-ce54b422baff"),
    CorpusImage(Subject.DOMESTIC_CAT, "1574158622682-e40e69881006"),
    CorpusImage(Subject.DOMESTIC_CAT, "1478098711619-5ab0b478d6e6"),
    CorpusImage(Subject.DOMESTIC_CAT, "1518791841217-8f162f1e1131"),
    CorpusImage(Subject.DOMESTIC_CAT, "1536589961747-e239b2abbec2"),
    CorpusImage(Subject.DOMESTIC_CAT, "1455970022149-a8f26b6902dd"),
    CorpusImage(Subject.DOMESTIC_CAT, "1604675223954-b1aabd668078"),
]
