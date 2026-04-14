from django.urls import path
from . import views

urlpatterns = [
    path("students/", views.StudentList.as_view(), name="student-list"),
    path("students/<uuid:pk>/", views.StudentDetail.as_view(), name="student-detail"),
    path(
        "attendance-records/",
        views.AttendanceRecordList.as_view(),
        name="attendance-record-list",
    ),
    path(
        "students/<uuid:student_pk>/attendance-records/<int:praktikum_day>/",
        views.AttendanceRecordDetail.as_view(),
        name="student-praktikum-attendance-record-detail",
    ),
    path(
        "paper-submissions/",
        views.PaperSubmissionList.as_view(),
        name="paper-submission-list",
    ),
    path(
        "paper-submissions/<uuid:student_pk>/<uuid:paper_id>/",
        views.PaperSubmissionDetail.as_view(),
        name="paper-submission-detail",
    ),
    path(
        "exercise-completions/",
        views.ExerciseCompletionList.as_view(),
        name="exercise-completion-list",
    ),
    path(
        "exercise-completions/<uuid:student_pk>/<uuid:exercise_id>/",
        views.ExerciseCompletionDetail.as_view(),
        name="exercise-completion-detail",
    ),
    path("final-results/", views.FinalResultList.as_view(), name="final-result-list"),
    path(
        "final-results/<uuid:pk>/",
        views.FinalResultDetail.as_view(),
        name="final-result-detail",
    ),
]
