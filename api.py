"""FastAPI app — the validated API + review surface (BRIEF.md §4 Flow B,
source brief's "Review API").

Two layers on the same data: a JSON API (/posts, /posts/{id}/images,
/pairings, /costs/summary) for programmatic use, and a single Jinja2 page
(/review) plus three form-post routes for a human reviewer — no
JavaScript, plain POST/redirect/GET.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from db import get_connection
from matching import rank_images_for_post
from pairings import create_pairing, list_pairings_for_review, review_pairing
from schemas import MatchResponse, PairingStatus, ReviewAction

app = FastAPI(title="Image Relevance & Auto-Tagging")
templates = Jinja2Templates(directory="templates")


class PostSummary(BaseModel):
    id: UUID
    title: str
    subject: str
    subject_confidence: float


class ImageSummary(BaseModel):
    id: UUID
    source_uri: str
    subject: str
    confidence: float


class CostSummaryRow(BaseModel):
    kind: str
    model: str
    calls: int
    ok_calls: int
    failed_calls: int
    total_cost_usd: float


class CostSummaryResponse(BaseModel):
    rows: list[CostSummaryRow]
    total_cost_usd: float


class PairingSummary(BaseModel):
    id: UUID
    post_id: UUID
    post_title: str
    image_id: UUID | None
    image_source_uri: str | None
    similarity: float | None
    verdict: str
    reason: str
    explanation: str
    status: str
    note: str | None


@app.get("/posts", response_model=list[PostSummary])
def get_posts() -> list[PostSummary]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select id, title, subject, subject_confidence from posts order by title")
            rows = cur.fetchall()
    return [
        PostSummary(id=post_id, title=title, subject=subject, subject_confidence=confidence)
        for post_id, title, subject, confidence in rows
    ]


@app.get("/images", response_model=list[ImageSummary])
def get_images() -> list[ImageSummary]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select i.id, i.source_uri, t.subject, t.confidence
                from images i
                join image_tags t on t.image_id = i.id
                where t.subject is not null
                order by t.subject, i.created_at
                """
            )
            rows = cur.fetchall()
    return [
        ImageSummary(id=image_id, source_uri=source_uri, subject=subject, confidence=confidence or 0.0)
        for image_id, source_uri, subject, confidence in rows
    ]


@app.get("/posts/{post_id}/images", response_model=MatchResponse)
async def get_post_images(post_id: UUID, force_image_id: UUID | None = None) -> MatchResponse:
    try:
        _pairing_id, decision = await create_pairing(post_id, force_image_id)
        ranked = [] if force_image_id is not None else rank_images_for_post(post_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MatchResponse(post_id=post_id, decision=decision, ranked=ranked)


@app.post("/pairings/{pairing_id}/review")
def post_pairing_review(pairing_id: UUID, action: ReviewAction) -> dict:
    try:
        review_pairing(pairing_id, action.action, action.note)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "no pairing" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return {"ok": True}


@app.get("/costs/summary", response_model=CostSummaryResponse)
def get_cost_summary() -> CostSummaryResponse:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select kind, model, count(*),
                       count(*) filter (where ok), count(*) filter (where not ok),
                       coalesce(sum(cost_usd), 0)
                from model_calls
                group by kind, model
                order by kind, model
                """
            )
            rows = cur.fetchall()
    cost_rows = [
        CostSummaryRow(
            kind=kind, model=model, calls=calls,
            ok_calls=ok_calls, failed_calls=failed_calls, total_cost_usd=float(total_cost),
        )
        for kind, model, calls, ok_calls, failed_calls, total_cost in rows
    ]
    return CostSummaryResponse(rows=cost_rows, total_cost_usd=sum(r.total_cost_usd for r in cost_rows))


@app.get("/pairings", response_model=list[PairingSummary])
def get_pairings() -> list[PairingSummary]:
    rows = list_pairings_for_review()
    return [
        PairingSummary(
            id=row["id"],
            post_id=row["post_id"],
            post_title=row["title"],
            image_id=row["image_id"],
            image_source_uri=row["source_uri"],
            similarity=row["similarity"],
            verdict=row["verdict"],
            reason=row["reason"],
            explanation=row["explanation"],
            status=row["status"],
            note=row["note"],
        )
        for row in rows
    ]


# --- Review page (server-rendered, no JS) ---------------------------------


@app.get("/review", response_class=HTMLResponse)
def review_page(request: Request) -> HTMLResponse:
    posts = get_posts()
    images = get_images()
    pairings = list_pairings_for_review()
    return templates.TemplateResponse(
        request,
        "review.html",
        {"posts": posts, "images": images, "pairings": pairings},
    )


@app.post("/review/suggest")
async def review_suggest(post_id: UUID = Form(...)) -> RedirectResponse:
    try:
        await create_pairing(post_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse(url="/review", status_code=303)


@app.post("/review/force")
async def review_force(post_id: UUID = Form(...), image_id: UUID = Form(...)) -> RedirectResponse:
    try:
        await create_pairing(post_id, image_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse(url="/review", status_code=303)


@app.post("/review/act")
def review_act(
    pairing_id: UUID = Form(...),
    action: PairingStatus = Form(...),
    note: str = Form(""),
) -> RedirectResponse:
    try:
        review_pairing(pairing_id, action, note or None)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "no pairing" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return RedirectResponse(url="/review", status_code=303)
