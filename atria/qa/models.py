from decimal import Decimal
from typing import Optional

from django.contrib.auth.models import User
from django.db import models


class Question(models.Model):
    """
    Knowledge economy question with dual-rail bounty support
    (Stripe fiat or Web3 crypto).
    """

    RAIL_NONE = "none"
    RAIL_STRIPE = "stripe"
    RAIL_CRYPTO = "crypto_evm"

    RAIL_CHOICES = [
        (RAIL_NONE, "No Bounty"),
        (RAIL_STRIPE, "Stripe (Fiat)"),
        (RAIL_CRYPTO, "Crypto EVM"),
    ]

    ESCROW_PENDING = "pending"
    ESCROW_LOCKED = "locked"
    ESCROW_RELEASED = "released"
    ESCROW_REFUNDED = "refunded"

    ESCROW_CHOICES = [
        (ESCROW_PENDING, "Pending"),
        (ESCROW_LOCKED, "Locked"),
        (ESCROW_RELEASED, "Released"),
        (ESCROW_REFUNDED, "Refunded"),
    ]

    STATUS_OPEN = "open"
    STATUS_ANSWERED = "answered"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_ANSWERED, "Answered"),
        (STATUS_CLOSED, "Closed"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="questions")

    bounty_amount = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal("0.00")
    )
    bounty_currency = models.CharField(max_length=10, default="USD")
    bounty_rail = models.CharField(
        max_length=20, choices=RAIL_CHOICES, default=RAIL_NONE, db_index=True
    )

    escrow_reference = models.CharField(max_length=255, blank=True, default="")
    escrow_status = models.CharField(
        max_length=20, choices=ESCROW_CHOICES, default=ESCROW_PENDING, db_index=True
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True
    )
    tags = models.JSONField(
        default=list, help_text="Topic tags e.g. ['python', 'web3', 'ai']"
    )
    views_count = models.PositiveIntegerField(default=0)

    accepted_answer = models.OneToOneField(
        "Answer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accepted_for_question",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["bounty_rail", "escrow_status"]),
        ]

    def __str__(self):
        return f"Q#{self.pk}: {self.title} ({self.status})"

    def is_bounty_active(self) -> bool:
        return self.bounty_amount > 0 and self.escrow_status == self.ESCROW_LOCKED

    def get_embedding_text(self) -> str:
        tag_str = ", ".join(self.tags) if self.tags else "general"
        return f"{self.title}\n{self.description}\nTopics: {tag_str}"


class Answer(models.Model):
    """
    Expert response submitted to a question.
    """

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="answers"
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="answers")
    content = models.TextField()
    is_accepted = models.BooleanField(default=False, db_index=True)

    upvotes = models.PositiveIntegerField(default=0)
    downvotes = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["question", "is_accepted"]),
            models.Index(fields=["question", "created_at"]),
        ]

    def __str__(self):
        return f"A#{self.pk} for Q#{self.question_id} by {self.author.username}"

    @property
    def score(self) -> int:
        return self.upvotes - self.downvotes


class AnswerVote(models.Model):
    """
    Track user votes on answers to prevent double-voting.
    """

    VOTE_UP = 1
    VOTE_DOWN = -1

    VOTE_CHOICES = [
        (VOTE_UP, "Upvote"),
        (VOTE_DOWN, "Downvote"),
    ]

    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="qa_votes")
    vote_type = models.SmallIntegerField(choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("answer", "user")

    def __str__(self):
        return f"Vote({self.vote_type}) by {self.user.username} on A#{self.answer_id}"


class Reputation(models.Model):
    """
    Decentralized knowledge reputation score, badges, and domain expertise per topic.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="reputation"
    )
    score = models.IntegerField(default=100)
    topic_scores = models.JSONField(
        default=dict,
        help_text="Reputation points by topic, e.g. {'python': 45, 'web3': 30}",
    )
    badges = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Reputation({self.user.username}: score={self.score})"

    def award_points(self, points: int, topic: Optional[str] = None):
        """
        Increment overall score and specific topic expertise score.
        """
        self.score += points
        if topic:
            current = self.topic_scores.get(topic, 0)
            self.topic_scores[topic] = max(0, current + points)
        self.check_badges()
        self.save()

    def check_badges(self):
        """
        Evaluate milestone badges based on score and achievements.
        """
        current_badges = set(self.badges)

        if self.score >= 200:
            current_badges.add("Contributor")
        if self.score >= 500:
            current_badges.add("Scholar")
        if self.score >= 1000:
            current_badges.add("Mastermind")

        # Topic specialist check
        for topic, pts in self.topic_scores.items():
            if pts >= 100:
                current_badges.add(f"{topic.capitalize()} Specialist")

        self.badges = sorted(list(current_badges))
