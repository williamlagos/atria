import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from feedly.ai import GeminiEmbeddingService
from feedly.moderation import ContentModerationService

from .models import Answer, AnswerVote, Question, Reputation

logger = logging.getLogger(__name__)


class QAService:
    """
    Core domain service managing Questions, Answers, AI Moderation,
    AI Embeddings, and Decentralized Reputation voting.
    """

    def __init__(
        self,
        embedding_service: Optional[GeminiEmbeddingService] = None,
        moderation_service: Optional[ContentModerationService] = None,
    ):
        self.embedding_service = embedding_service or GeminiEmbeddingService()
        self.moderation_service = moderation_service or ContentModerationService()

    def create_question(
        self,
        title: str,
        description: str,
        author: User,
        tags: Optional[List[str]] = None,
        bounty_amount: Decimal = Decimal("0.00"),
        bounty_rail: str = Question.RAIL_NONE,
        bounty_currency: str = "USD",
        escrow_reference: str = "",
    ) -> Question:
        """
        Create a new question with automated AI safety moderation
        and semantic embedding.
        """
        full_text = f"{title}\n{description}"

        # 1. AI Safety Moderation
        mod_result = self.moderation_service.moderate_text(full_text, author=author)
        if mod_result["status"] in ["flagged", "rejected"]:
            raise ValueError(
                f"Question rejected by AI safety policy: {mod_result['reason']}"
            )

        # 2. Persist Question
        question = Question.objects.create(
            title=title.strip(),
            description=description.strip(),
            author=author,
            tags=tags or [],
            bounty_amount=bounty_amount,
            bounty_rail=bounty_rail,
            bounty_currency=bounty_currency,
            escrow_reference=escrow_reference,
            escrow_status=(
                Question.ESCROW_LOCKED if escrow_reference else Question.ESCROW_PENDING
            ),
        )

        # 3. Create Audit Moderation Record
        self.moderation_service.moderate_object(question, text=full_text, author=author)

        # 4. Generate Semantic Vector Embedding
        try:
            self.embedding_service.embed_object(
                question, text=question.get_embedding_text()
            )
        except Exception as e:
            logger.warning("Could not generate embedding for Q#%d: %s", question.pk, e)

        return question

    def create_answer(
        self,
        question: Question,
        content: str,
        author: User,
    ) -> Answer:
        """
        Submit an answer with AI moderation check.
        """
        # 1. AI Safety Moderation
        mod_result = self.moderation_service.moderate_text(content, author=author)
        if mod_result["status"] in ["flagged", "rejected"]:
            raise ValueError(
                f"Answer rejected by AI safety policy: {mod_result['reason']}"
            )

        # 2. Persist Answer
        answer = Answer.objects.create(
            question=question,
            author=author,
            content=content.strip(),
        )

        # 3. Audit Moderation Record
        self.moderation_service.moderate_object(answer, text=content, author=author)

        return answer

    def vote_answer(
        self,
        answer: Answer,
        user: User,
        vote_type: int,
    ) -> Dict[str, Any]:
        """
        Record upvote or downvote, updating answer totals and author reputation.
        """
        if vote_type not in [AnswerVote.VOTE_UP, AnswerVote.VOTE_DOWN]:
            raise ValueError("Invalid vote type: must be 1 (upvote) or -1 (downvote).")

        if answer.author == user:
            raise PermissionError("Users cannot vote on their own answers.")

        vote, created = AnswerVote.objects.get_or_create(
            answer=answer,
            user=user,
            defaults={"vote_type": vote_type},
        )

        rep, _ = Reputation.objects.get_or_create(user=answer.author)

        if not created:
            if vote.vote_type == vote_type:
                # Cancel existing vote
                if vote.vote_type == AnswerVote.VOTE_UP:
                    answer.upvotes = max(0, answer.upvotes - 1)
                    rep.award_points(-10)
                else:
                    answer.downvotes = max(0, answer.downvotes - 1)
                    rep.award_points(2)
                vote.delete()
                current_vote = 0
            else:
                # Switch vote direction
                if vote_type == AnswerVote.VOTE_UP:
                    answer.downvotes = max(0, answer.downvotes - 1)
                    answer.upvotes += 1
                    rep.award_points(12)  # Revert -2 and add +10
                else:
                    answer.upvotes = max(0, answer.upvotes - 1)
                    answer.downvotes += 1
                    rep.award_points(-12)  # Revert +10 and subtract -2
                vote.vote_type = vote_type
                vote.save(update_fields=["vote_type"])
                current_vote = vote_type
        else:
            # New vote
            if vote_type == AnswerVote.VOTE_UP:
                answer.upvotes += 1
                rep.award_points(10)
            else:
                answer.downvotes += 1
                rep.award_points(-2)
            current_vote = vote_type

        answer.save(update_fields=["upvotes", "downvotes"])

        return {
            "answer_id": answer.pk,
            "upvotes": answer.upvotes,
            "downvotes": answer.downvotes,
            "score": answer.score,
            "user_vote": current_vote,
            "author_reputation": rep.score,
        }

    def get_related_questions(
        self,
        question: Question,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve semantically similar questions using vector embeddings.
        """
        ct = ContentType.objects.get_for_model(Question)
        results = self.embedding_service.search_similar(
            query=question.get_embedding_text(),
            content_type=ct,
            top_k=top_k + 1,
            min_score=0.1,
        )

        # Exclude self
        filtered = []
        for r in results:
            obj = r["object"]
            if obj and obj.pk != question.pk:
                filtered.append(
                    {
                        "id": obj.pk,
                        "title": obj.title,
                        "status": obj.status,
                        "score": r["score"],
                        "bounty": str(obj.bounty_amount),
                    }
                )
        return filtered[:top_k]

    def get_ai_summary_and_suggestions(
        self,
        question: Question,
    ) -> Dict[str, Any]:
        """
        Generate an AI synthesis of answers or guidance suggestions for open questions.
        """
        answers = list(question.answers.all().order_by("-upvotes", "created_at"))

        if not answers:
            return {
                "summary": (
                    "No answers submitted yet. Post an answer to claim the bounty!"
                ),
                "key_takeaways": [],
                "consensus_level": "none",
                "suggested_topics": question.tags,
            }

        # Build prompt for Gemini if available
        if self.embedding_service.client:
            try:
                answers_text = "\n---\n".join(
                    [
                        f"Answer by @{a.author.username} (+{a.score}): {a.content}"
                        for a in answers[:5]
                    ]
                )
                prompt = (
                    "Summarize insights from the answers to this question:\n"
                    f"Title: {question.title}\n"
                    f"Description: {question.description}\n\n"
                    f"Answers:\n{answers_text}\n\n"
                    "Provide a concise summary in 2 sentences."
                )
                response = self.embedding_service.client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=prompt,
                )
                summary = response.text.strip()
            except Exception as e:
                logger.error("AI QA synthesis error: %s", e)
                summary = answers[0].content[:200] + "..."
        else:
            top_answer = answers[0]
            summary = (
                f"Top response by @{top_answer.author.username} "
                f"({top_answer.score} points): {top_answer.content[:200]}..."
            )

        return {
            "summary": summary,
            "total_answers": len(answers),
            "accepted_answer_id": question.accepted_answer_id,
            "top_answer_id": answers[0].pk,
            "suggested_topics": question.tags,
        }
