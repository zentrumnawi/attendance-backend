from rest_framework import generics
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.http import Http404
from django.shortcuts import get_object_or_404
from .models import (
    Student,
    AttendanceRecord,
    PaperSubmission,
    ExerciseCompletion,
    FinalResult,
    Group,
    Department,
    Experiment,
    Paper,
    Exercise,
    UserProfile,
)

from .serializers import (
    StudentSerializer,
    AttendanceRecordSerializer,
    PaperSubmissionSerializer,
    ExerciseCompletionSerializer,
    FinalResultSerializer,
    GroupSerializer,
    DepartmentSerializer,
    ExperimentSerializer,
    PaperSerializer,
    ExerciseSerializer,
    UserProfileSerializer,
)


class StudentList(generics.ListCreateAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Student.objects.all()
        try:
            user_group = self.request.user.userprofile.group
            return Student.objects.filter(group=user_group)
        except UserProfile.DoesNotExist:
            return Student.objects.none()


class StudentDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer


# Get attendance records (according to permissions): in toto , by day or by student
class AttendanceRecordList(generics.ListCreateAPIView):
    queryset = AttendanceRecord.objects.all()
    serializer_class = AttendanceRecordSerializer

    def get_queryset(self):
        queryset = AttendanceRecord.objects.for_user(self.request.user)
        day_param = self.request.query_params.get("day")
        student_pk = self.request.query_params.get("student_pk")

        if day_param:
            try:
                day = int(day_param)
                queryset = queryset.filter(praktikum_day=day)
            except ValueError:
                pass

        if student_pk:
            queryset = queryset.filter(student__pk=student_pk)

        return queryset


# get single attendance record
class AttendanceRecordDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AttendanceRecordSerializer

    def get_object(self):
        student_pk = self.kwargs.get("student_pk")
        praktikum_day = self.kwargs.get("praktikum_day")

        base_queryset = AttendanceRecord.objects.for_user(self.request.user)

        if student_pk and praktikum_day is not None:
            obj = get_object_or_404(
                base_queryset, student__pk=student_pk, praktikum_day=praktikum_day
            )

        else:
            raise Http404("Please provide 'student_pk' and 'praktikum_day'.")

        return obj


class PaperSubmissionList(generics.ListCreateAPIView):
    queryset = PaperSubmission.objects.all()
    serializer_class = PaperSubmissionSerializer

    def get_queryset(self):
        paper_id = self.request.query_params.get("paper_id")
        if paper_id:
            try:
                return PaperSubmission.objects.for_user(self.request.user).filter(
                    paper__pk=paper_id
                )
            except Paper.DoesNotExist:
                raise Http404("Paper not found")
        else:
            return PaperSubmission.objects.for_user(self.request.user)


class PaperSubmissionDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PaperSubmissionSerializer
    queryset = PaperSubmission.objects.all()

    def get_object(self):
        student_pk = self.kwargs.get("student_pk")
        paper_id = self.kwargs.get("paper_id")

        base_queryset = PaperSubmission.objects.for_user(self.request.user)

        if student_pk and paper_id is not None:
            obj = get_object_or_404(
                base_queryset, student__pk=student_pk, paper__pk=paper_id
            )

        else:
            raise Http404("Please provide 'student_pk' and 'paper_id'.")

        return obj


class ExerciseCompletionList(generics.ListCreateAPIView):
    queryset = ExerciseCompletion.objects.all()
    serializer_class = ExerciseCompletionSerializer

    def get_queryset(self):
        exercise_id = self.request.query_params.get("exercise_id")
        if exercise_id:
            try:
                return ExerciseCompletion.objects.for_user(self.request.user).filter(
                    exercise__pk=exercise_id
                )
            except Exercise.DoesNotExist:
                raise Http404("Exercise not found")
        else:
            return ExerciseCompletion.objects.for_user(self.request.user)


class ExerciseCompletionDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ExerciseCompletionSerializer

    def get_object(self):
        student_pk = self.kwargs.get("student_pk")
        exercise_id = self.kwargs.get("exercise_id")

        base_queryset = ExerciseCompletion.objects.for_user(self.request.user)

        if student_pk and exercise_id is not None:
            obj = get_object_or_404(
                base_queryset, student__pk=student_pk, exercise__pk=exercise_id
            )

        else:
            raise Http404("Please provide 'student_pk' and 'exercise_id'.")

        return obj


class FinalResultList(generics.ListCreateAPIView):
    queryset = FinalResult.objects.all()
    serializer_class = FinalResultSerializer

    def get_queryset(self):
        return FinalResult.objects.for_user(self.request.user)


class FinalResultDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = FinalResult.objects.all()
    serializer_class = FinalResultSerializer
