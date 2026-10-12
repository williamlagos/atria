from django.urls import path

from .views import AnswerFederationView, QuestionFederationView

urlpatterns = [
    path(
        "questions/<int:question_id>",
        QuestionFederationView.as_view(),
        name="qa-question-federation",
    ),
    path(
        "answers/<int:answer_id>",
        AnswerFederationView.as_view(),
        name="qa-answer-federation",
    ),
]
