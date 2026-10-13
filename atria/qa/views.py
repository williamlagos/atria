from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from .federation import answer_to_activitypub, question_to_activitypub
from .models import Answer, Question


class QuestionFederationView(View):
    """
    Expose Question as an ActivityStreams 2.0 object.
    """

    def get(self, request, question_id):
        question = get_object_or_404(Question, pk=question_id)
        doc = question_to_activitypub(question, request)
        return JsonResponse(
            doc,
            content_type="application/activity+json",
        )


class AnswerFederationView(View):
    """
    Expose Answer as an ActivityStreams 2.0 Note object.
    """

    def get(self, request, answer_id):
        answer = get_object_or_404(Answer, pk=answer_id)
        doc = answer_to_activitypub(answer, request)
        return JsonResponse(
            doc,
            content_type="application/activity+json",
        )
