"""Social and ActivityPub federation router for Atria."""

from typing import Any, Dict, List, Optional

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError
from socialize.models import Activity, Actor, Follow, Object

social_router = Router()


class ActorOut(Schema):
    id: str
    username: str
    display_name: Optional[str] = None
    bio: str
    score: int
    actor_type: str
    actor_url: str
    inbox: str
    outbox: str


class FollowIn(Schema):
    target_username: str


class FollowOut(Schema):
    actor: str
    target: str
    accepted: bool
    created_at: str


class ActivityIn(Schema):
    activity_type: str = "Create"
    object_type: str = "Note"
    content: str
    summary: str = ""


class ActivityOut(Schema):
    id: str
    activity_type: str
    actor: str
    activity_url: str
    published_at: str
    object: Dict[str, Any]


def get_or_create_actor_for_user(user: User) -> Actor:
    """Helper to retrieve or lazily create an Actor instance for a User."""
    actor, _ = Actor.objects.get_or_create(
        user=user,
        defaults={
            "username": user.username,
            "display_name": f"{user.first_name} {user.last_name}".strip()
            or user.username,
        },
    )
    return actor


@social_router.get("/actors", response=List[ActorOut])
def list_actors(request, limit: int = 20, offset: int = 0):
    """Lists federated actors across the instance."""
    actors = Actor.objects.all().order_by("-joined_at")[offset : offset + limit]
    results = []
    for a in actors:
        results.append(
            {
                "id": str(a.pk),
                "username": a.get_username(),
                "display_name": a.get_display_name(),
                "bio": a.bio,
                "score": a.score,
                "actor_type": a.actor_type,
                "actor_url": a.get_actor_url(),
                "inbox": a.get_inbox_url(),
                "outbox": a.get_outbox_url(),
            }
        )
    return results


@social_router.get("/actors/{username}", response=ActorOut)
def get_actor_detail(request, username: str):
    """Retrieves an actor's profile and federation metadata by username."""
    actor = Actor.objects.filter(username=username).first()
    if not actor:
        user = get_object_or_404(User, username=username)
        actor = get_or_create_actor_for_user(user)

    return {
        "id": str(actor.pk),
        "username": actor.get_username(),
        "display_name": actor.get_display_name(),
        "bio": actor.bio,
        "score": actor.score,
        "actor_type": actor.actor_type,
        "actor_url": actor.get_actor_url(),
        "inbox": actor.get_inbox_url(),
        "outbox": actor.get_outbox_url(),
    }


@social_router.post("/follow", response=FollowOut)
def follow_actor(request, payload: FollowIn):
    """Creates a follow relationship from the authenticated user to a target actor."""
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required to follow actors")

    current_actor = get_or_create_actor_for_user(request.user)
    target_actor = Actor.objects.filter(username=payload.target_username).first()
    if not target_actor:
        target_user = get_object_or_404(User, username=payload.target_username)
        target_actor = get_or_create_actor_for_user(target_user)

    if current_actor.pk == target_actor.pk:
        raise HttpError(400, "Cannot follow yourself")

    follow, created = Follow.objects.get_or_create(
        actor=current_actor,
        target=target_actor,
        defaults={"accepted": True},
    )

    if created:
        Activity.objects.create(
            actor=current_actor,
            activity_type="Follow",
            object_data=target_actor.get_actor_url(),
        )

    return {
        "actor": current_actor.get_username(),
        "target": target_actor.get_username(),
        "accepted": follow.accepted,
        "created_at": follow.created_at.isoformat(),
    }


@social_router.post("/unfollow")
def unfollow_actor(request, payload: FollowIn):
    """Removes a follow relationship between the current user and target actor."""
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required")

    current_actor = get_or_create_actor_for_user(request.user)
    target_actor = Actor.objects.filter(username=payload.target_username).first()
    if not target_actor:
        target_user = get_object_or_404(User, username=payload.target_username)
        target_actor = get_or_create_actor_for_user(target_user)

    deleted_count, _ = Follow.objects.filter(
        actor=current_actor, target=target_actor
    ).delete()

    if deleted_count:
        Activity.objects.create(
            actor=current_actor,
            activity_type="Undo",
            object_data={
                "type": "Follow",
                "actor": current_actor.get_actor_url(),
                "object": target_actor.get_actor_url(),
            },
        )

    return {"status": "unfollowed", "target": payload.target_username}


@social_router.get("/actors/{username}/followers", response=List[ActorOut])
def get_actor_followers(request, username: str):
    """Returns actors that follow the given user."""
    actor = Actor.objects.filter(username=username).first()
    if not actor:
        user = get_object_or_404(User, username=username)
        actor = get_or_create_actor_for_user(user)

    follows = Follow.objects.filter(target=actor, accepted=True).select_related("actor")
    return [
        {
            "id": str(f.actor.pk),
            "username": f.actor.get_username(),
            "display_name": f.actor.get_display_name(),
            "bio": f.actor.bio,
            "score": f.actor.score,
            "actor_type": f.actor.actor_type,
            "actor_url": f.actor.get_actor_url(),
            "inbox": f.actor.get_inbox_url(),
            "outbox": f.actor.get_outbox_url(),
        }
        for f in follows
    ]


@social_router.get("/actors/{username}/following", response=List[ActorOut])
def get_actor_following(request, username: str):
    """Returns actors that the given user follows."""
    actor = Actor.objects.filter(username=username).first()
    if not actor:
        user = get_object_or_404(User, username=username)
        actor = get_or_create_actor_for_user(user)

    follows = Follow.objects.filter(actor=actor, accepted=True).select_related("target")
    return [
        {
            "id": str(f.target.pk),
            "username": f.target.get_username(),
            "display_name": f.target.get_display_name(),
            "bio": f.target.bio,
            "score": f.target.score,
            "actor_type": f.target.actor_type,
            "actor_url": f.target.get_actor_url(),
            "inbox": f.target.get_inbox_url(),
            "outbox": f.target.get_outbox_url(),
        }
        for f in follows
    ]


@social_router.get("/actors/{username}/outbox", response=List[ActivityOut])
def get_actor_outbox(request, username: str, limit: int = 20, offset: int = 0):
    """Retrieves activities authored by the specified actor."""
    actor = Actor.objects.filter(username=username).first()
    if not actor:
        user = get_object_or_404(User, username=username)
        actor = get_or_create_actor_for_user(user)

    activities = Activity.objects.filter(actor=actor).order_by("-published_at")[
        offset : offset + limit
    ]
    return [
        {
            "id": str(act.pk),
            "activity_type": act.activity_type,
            "actor": actor.get_username(),
            "activity_url": act.get_activity_url(),
            "published_at": act.published_at.isoformat(),
            "object": act.object_data if isinstance(act.object_data, dict) else {},
        }
        for act in activities
    ]


@social_router.post("/activities", response=ActivityOut)
def create_activity(request, payload: ActivityIn):
    """
    Publishes a new ActivityPub activity (Note, Article, etc.) for current user.
    """
    if not request.user.is_authenticated:

        raise HttpError(401, "Authentication required to create activities")

    actor = get_or_create_actor_for_user(request.user)

    obj = Object.objects.create(
        actor=actor,
        object_type=payload.object_type,
        content=payload.content,
        summary=payload.summary,
    )

    activity = Activity.objects.create(
        actor=actor,
        activity_type=payload.activity_type,
        object_data=obj.as_activitypub(),
    )

    return {
        "id": str(activity.pk),
        "activity_type": activity.activity_type,
        "actor": actor.get_username(),
        "activity_url": activity.get_activity_url(),
        "published_at": activity.published_at.isoformat(),
        "object": activity.object_data,
    }
