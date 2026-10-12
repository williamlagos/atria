from typing import Any, Dict

from django.conf import settings
from django.http import HttpRequest

from .models import Answer, Question


def get_base_url(request: HttpRequest = None) -> str:
    domain = getattr(settings, "SITE_DOMAIN", "localhost:8000")
    scheme = "https" if not settings.DEBUG else "http"
    if request:
        return f"{scheme}://{request.get_host()}"
    return f"{scheme}://{domain}"


def question_to_activitypub(
    question: Question, request: HttpRequest = None
) -> Dict[str, Any]:
    """
    Format Question model instance as an ActivityStreams 2.0 Question object.
    """
    base_url = get_base_url(request)
    actor_url = f"{base_url}/u/{question.author.username}"
    question_url = f"{base_url}/qa/questions/{question.pk}"

    tags_ap = [
        {"type": "Hashtag", "name": f"#{tag}", "href": f"{base_url}/tags/{tag}"}
        for tag in question.tags
    ]

    doc = {
        "@context": [
            "https://www.w3.org/ns/activitystreams",
            {"atria": "https://atria.network/ns#"},
        ],
        "id": question_url,
        "type": "Question",
        "name": question.title,
        "content": question.description,
        "attributedTo": actor_url,
        "published": question.created_at.isoformat(),
        "updated": question.updated_at.isoformat(),
        "to": ["https://www.w3.org/ns/activitystreams#Public"],
        "tag": tags_ap,
        "atria:status": question.status,
        "atria:bounty": {
            "amount": str(question.bounty_amount),
            "currency": question.bounty_currency,
            "rail": question.bounty_rail,
            "escrow_status": question.escrow_status,
        },
    }

    if question.accepted_answer_id:
        doc["atria:acceptedAnswer"] = (
            f"{base_url}/qa/answers/{question.accepted_answer_id}"
        )

    return doc


def answer_to_activitypub(
    answer: Answer, request: HttpRequest = None
) -> Dict[str, Any]:
    """
    Format Answer model instance as an ActivityStreams 2.0 Note object
    in reply to the Question.
    """
    base_url = get_base_url(request)
    actor_url = f"{base_url}/u/{answer.author.username}"
    answer_url = f"{base_url}/qa/answers/{answer.pk}"
    question_url = f"{base_url}/qa/questions/{answer.question_id}"

    return {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": answer_url,
        "type": "Note",
        "content": answer.content,
        "attributedTo": actor_url,
        "inReplyTo": question_url,
        "published": answer.created_at.isoformat(),
        "updated": answer.updated_at.isoformat(),
        "to": ["https://www.w3.org/ns/activitystreams#Public"],
        "upvotes": answer.upvotes,
        "isAccepted": answer.is_accepted,
    }
