from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from .escrow import BountyEscrowService
from .models import Answer, Question, Reputation
from .services import QAService

qa_router = Router()


class QuestionIn(Schema):
    title: str
    description: str
    tags: List[str] = []
    bounty_amount: str = "0.00"
    bounty_rail: str = "none"
    bounty_currency: str = "USD"
    escrow_reference: str = ""


class QuestionOut(Schema):
    id: int
    title: str
    description: str
    author: str
    status: str
    bounty_amount: str
    bounty_rail: str
    bounty_currency: str
    escrow_status: str
    tags: List[str]
    views_count: int
    accepted_answer_id: Optional[int] = None
    created_at: str


class AnswerIn(Schema):
    content: str


class AnswerOut(Schema):
    id: int
    question_id: int
    author: str
    content: str
    is_accepted: bool
    score: int
    upvotes: int
    downvotes: int
    created_at: str


class VoteIn(Schema):
    vote_type: int


class ReputationOut(Schema):
    username: str
    score: int
    topic_scores: Dict[str, int]
    badges: List[str]


def _format_question(q: Question) -> Dict[str, Any]:
    return {
        "id": q.pk,
        "title": q.title,
        "description": q.description,
        "author": q.author.username,
        "status": q.status,
        "bounty_amount": str(q.bounty_amount),
        "bounty_rail": q.bounty_rail,
        "bounty_currency": q.bounty_currency,
        "escrow_status": q.escrow_status,
        "tags": q.tags,
        "views_count": q.views_count,
        "accepted_answer_id": q.accepted_answer_id,
        "created_at": q.created_at.isoformat(),
    }


def _format_answer(a: Answer) -> Dict[str, Any]:
    return {
        "id": a.pk,
        "question_id": a.question_id,
        "author": a.author.username,
        "content": a.content,
        "is_accepted": a.is_accepted,
        "score": a.score,
        "upvotes": a.upvotes,
        "downvotes": a.downvotes,
        "created_at": a.created_at.isoformat(),
    }


@qa_router.get("/questions", response=List[QuestionOut])
def list_questions(
    request,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    bounty_rail: Optional[str] = None,
    limit: int = 20,
):
    """List questions with optional filters (status, tag, bounty_rail)."""
    qs = Question.objects.all().select_related("author").order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    if bounty_rail:
        qs = qs.filter(bounty_rail=bounty_rail)
    if tag:
        qs = qs.filter(tags__contains=[tag])

    return [_format_question(q) for q in qs[:limit]]


@qa_router.post(
    "/questions", response={201: QuestionOut, 400: Dict[str, str], 401: Dict[str, str]}
)
def create_question(request, payload: QuestionIn):
    """
    Ask a question with AI safety moderation, embedding generation,
    and optional bounty.
    """
    if not request.user.is_authenticated:
        return 401, {"error": "Authentication required to ask a question."}

    service = QAService()
    try:
        bounty_val = Decimal(payload.bounty_amount)
    except Exception:
        return 400, {"error": "Invalid bounty_amount format."}

    try:
        question = service.create_question(
            title=payload.title,
            description=payload.description,
            author=request.user,
            tags=payload.tags,
            bounty_amount=bounty_val,
            bounty_rail=payload.bounty_rail,
            bounty_currency=payload.bounty_currency,
            escrow_reference=payload.escrow_reference,
        )
        return 201, _format_question(question)
    except ValueError as e:
        return 400, {"error": str(e)}


@qa_router.get("/questions/{int:question_id}")
def get_question_details(request, question_id: int):
    """Retrieve full details of a question, its answers, and AI answer synthesis."""
    question = get_object_or_404(
        Question.objects.select_related("author"), pk=question_id
    )
    # Increment views
    Question.objects.filter(pk=question_id).update(views_count=question.views_count + 1)
    question.views_count += 1

    answers = [
        _format_answer(a)
        for a in question.answers.all()
        .select_related("author")
        .order_by("-is_accepted", "-upvotes")
    ]

    service = QAService()
    ai_data = service.get_ai_summary_and_suggestions(question)

    return {
        "question": _format_question(question),
        "answers": answers,
        "ai_synthesis": ai_data,
    }


@qa_router.post(
    "/questions/{int:question_id}/answers",
    response={201: AnswerOut, 400: Dict[str, str], 401: Dict[str, str]},
)
def create_answer(request, question_id: int, payload: AnswerIn):
    """Submit an answer to an existing question with AI content moderation."""
    if not request.user.is_authenticated:
        return 401, {"error": "Authentication required to answer a question."}

    question = get_object_or_404(Question, pk=question_id)
    if question.status == Question.STATUS_CLOSED:
        return 400, {"error": "Cannot answer a closed question."}

    service = QAService()
    try:
        answer = service.create_answer(
            question=question,
            content=payload.content,
            author=request.user,
        )
        return 201, _format_answer(answer)
    except ValueError as e:
        return 400, {"error": str(e)}


@qa_router.post(
    "/questions/{int:question_id}/accept/{int:answer_id}",
    response={
        200: Dict[str, Any],
        400: Dict[str, str],
        401: Dict[str, str],
        403: Dict[str, str],
    },
)
def accept_answer(request, question_id: int, answer_id: int):
    """Accept an answer, close question, release bounty escrow, and award reputation."""
    if not request.user.is_authenticated:
        return 401, {"error": "Authentication required."}

    question = get_object_or_404(Question, pk=question_id)
    answer = get_object_or_404(Answer, pk=answer_id)

    escrow_service = BountyEscrowService()
    try:
        result = escrow_service.release_bounty(question, answer, request.user)
        return 200, result
    except PermissionError as e:
        return 403, {"error": str(e)}
    except ValueError as e:
        return 400, {"error": str(e)}


@qa_router.post(
    "/answers/{int:answer_id}/vote",
    response={
        200: Dict[str, Any],
        400: Dict[str, str],
        401: Dict[str, str],
        403: Dict[str, str],
    },
)
def vote_answer(request, answer_id: int, payload: VoteIn):
    """Upvote or downvote an answer, affecting score and author reputation."""
    if not request.user.is_authenticated:
        return 401, {"error": "Authentication required."}

    answer = get_object_or_404(Answer, pk=answer_id)
    service = QAService()
    try:
        res = service.vote_answer(answer, request.user, payload.vote_type)
        return 200, res
    except PermissionError as e:
        return 403, {"error": str(e)}
    except ValueError as e:
        return 400, {"error": str(e)}


@qa_router.get("/questions/{int:question_id}/related")
def get_related_questions(request, question_id: int, limit: int = 5):
    """Retrieve semantically related questions using vector embeddings."""
    question = get_object_or_404(Question, pk=question_id)
    service = QAService()
    related = service.get_related_questions(question, top_k=limit)
    return {"question_id": question_id, "related": related}


@qa_router.get(
    "/reputation/{str:username}", response={200: ReputationOut, 404: Dict[str, str]}
)
def get_user_reputation(request, username: str):
    """Get public reputation score, badges, and topic expertise."""
    user = get_object_or_404(User, username=username)
    rep, _ = Reputation.objects.get_or_create(user=user)
    return 200, {
        "username": user.username,
        "score": rep.score,
        "topic_scores": rep.topic_scores,
        "badges": rep.badges,
    }
