"""AI feeds, semantic discovery, and content moderation router for Atria."""

from typing import List, Optional

from feedly.ai import GeminiEmbeddingService
from feedly.models import Page, UserInterestProfile
from feedly.moderation import ContentModerationService
from feedly.ranking import FeedRanker
from ninja import Router, Schema
from ninja.errors import HttpError

feeds_router = Router()


class FeedItemOut(Schema):
    id: int
    title: str
    content: str
    date: str
    author: Optional[str] = None
    score: Optional[float] = None


class SearchResultOut(Schema):
    object_id: int
    content_type: Optional[str] = None
    text_snippet: str
    score: float


class SemanticSearchIn(Schema):
    query: str
    limit: int = 10
    min_score: float = 0.0


class InterestProfileIn(Schema):
    topics: List[str] = []


class InterestProfileOut(Schema):
    username: str
    topics: List[str]


class ModerationIn(Schema):
    content: str


class ModerationOut(Schema):
    status: str
    is_approved: bool
    is_quarantined: bool
    flags: List[str]
    reason: str


@feeds_router.get("/chronological", response=List[FeedItemOut])
def get_chronological_feed(request, limit: int = 20, offset: int = 0):
    """
    Retrieves time-ordered chronological feed items with safety filtering.
    """
    ranker = FeedRanker()
    items = Page.objects.all().select_related("user")
    ranked = ranker.get_chronological_feed(items, limit=limit, offset=offset)
    return [
        {
            "id": p.pk,
            "title": getattr(p, "name", str(p)),
            "content": getattr(p, "content", ""),
            "date": p.date.isoformat(),
            "author": p.user.username if p.user else None,
            "score": None,
        }
        for p in ranked
    ]


@feeds_router.get("/trending", response=List[FeedItemOut])
def get_trending_feed(request, limit: int = 20, gravity: float = 1.5):
    """Retrieves trending feed items ranked by Hacker News gravity decay."""
    ranker = FeedRanker()
    items = Page.objects.all().select_related("user")
    ranked = ranker.get_trending_feed(items, limit=limit, gravity=gravity)
    return [
        {
            "id": entry["item"].pk,
            "title": getattr(entry["item"], "name", str(entry["item"])),
            "content": getattr(entry["item"], "content", ""),
            "date": entry["item"].date.isoformat(),
            "author": entry["item"].user.username if entry["item"].user else None,
            "score": entry["score"],
        }
        for entry in ranked
    ]


@feeds_router.get("/personalized", response=List[FeedItemOut])
def get_personalized_feed(request, limit: int = 20):
    """
    Retrieves personalized feed blending follow graph, semantic vector, and recency.
    """
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required for personalized feed")

    ranker = FeedRanker()
    items = Page.objects.all().select_related("user")
    ranked = ranker.get_personalized_feed(request.user, items, limit=limit)
    return [
        {
            "id": entry["item"].pk,
            "title": getattr(entry["item"], "name", str(entry["item"])),
            "content": getattr(entry["item"], "content", ""),
            "date": entry["item"].date.isoformat(),
            "author": entry["item"].user.username if entry["item"].user else None,
            "score": entry["score"],
        }
        for entry in ranked
    ]


@feeds_router.post("/search", response=List[SearchResultOut])
def semantic_search(request, payload: SemanticSearchIn):
    """Performs cosine-similarity vector search across embedded content using Gemini."""
    service = GeminiEmbeddingService()
    results = service.search_similar(
        query=payload.query,
        top_k=payload.limit,
        min_score=payload.min_score,
    )
    return [
        {
            "object_id": r["object_id"],
            "content_type": r["content_type"],
            "text_snippet": r["text_snippet"],
            "score": r["score"],
        }
        for r in results
    ]


@feeds_router.get("/interests", response=InterestProfileOut)
def get_user_interests(request):
    """Retrieves semantic interest topics for the active user."""
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required")

    profile, _ = UserInterestProfile.objects.get_or_create(user=request.user)
    return {
        "username": request.user.username,
        "topics": profile.topics,
    }


@feeds_router.post("/interests", response=InterestProfileOut)
def update_user_interests(request, payload: InterestProfileIn):
    """
    Updates user interest topics and regenerates their semantic profile embedding.
    """
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required")

    ranker = FeedRanker()
    profile = ranker.update_user_interest_vector(
        user=request.user, topics=payload.topics
    )
    return {
        "username": request.user.username,
        "topics": profile.topics,
    }


@feeds_router.post("/moderate", response=ModerationOut)
def moderate_content(request, payload: ModerationIn):
    """
    Evaluates text against AI safety categories (toxicity, harassment, spam, danger).
    """
    service = ContentModerationService()
    res = service.moderate_text(
        payload.content,
        author=request.user if request.user.is_authenticated else None,
    )
    return {
        "status": res["status"],
        "is_approved": res["status"] == "approved",
        "is_quarantined": res["status"] != "approved",
        "flags": res.get("flagged_categories", []),
        "reason": res.get("reason", ""),
    }
