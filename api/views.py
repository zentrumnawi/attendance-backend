from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import (
    Student,
    AttendanceRecord,
    LabDay,
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
    AttendanceRecordBulkSerializer,
    AttendanceRecordBulkItemSerializer,
    PaperSubmissionSerializer,
    PaperSubmissionBulkSerializer,
    MinimalStudentSerializer,
    ExerciseCompletionSerializer,
    FinalResultSerializer,
    GroupSerializer,
    DepartmentSerializer,
    ExperimentSerializer,
    PaperSerializer,
    ExerciseSerializer,
    UserProfileSerializer,
)

from .utils.csv_import import validate_and_parse_csv_file, bulk_import_students


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

    def get_object(self):
        if self.request.user.is_superuser:
            return get_object_or_404(Student, pk=self.kwargs.get("pk"))
        try:
            user_group = self.request.user.userprofile.group
            return get_object_or_404(
                Student, pk=self.kwargs.get("pk"), group=user_group
            )
        except UserProfile.DoesNotExist:
            raise Http404("Student not found")


# Get attendance records (according to permissions): in toto, by date or by student
class AttendanceRecordList(generics.ListCreateAPIView):
    queryset = AttendanceRecord.objects.all()
    serializer_class = AttendanceRecordSerializer

    def get_queryset(self):
        queryset = AttendanceRecord.objects.for_user(self.request.user)
        date_param = self.request.query_params.get("date")
        student_pk = self.request.query_params.get("student_pk")

        if date_param:
            parsed_date = parse_date(date_param)
            if parsed_date:
                queryset = queryset.filter(date=parsed_date)

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


class AttendanceCalendarView(APIView):
    """Roll-call dates for the calendar"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = LabDay.objects.for_user(request.user)

        lab_days = list(queryset.order_by("date"))

        return Response(
            {
                "dates": [
                    {
                        "date": lab_day.date.isoformat(),
                        "praktikum_day": lab_day.praktikum_day,
                        "group": lab_day.group.name,
                    }
                    for lab_day in lab_days
                ]
            }
        )


class AttendanceRecordBulkCreateView(APIView):
    """Create or update all attendance records for one roll-call session"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AttendanceRecordBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # check for duplicate student_id in records
        student_ids = [item["student_id"] for item in data["records"]]
        if len(student_ids) != len(set(student_ids)):
            raise ValidationError({"records": "Duplicate student_id in records."})

        saved_records = []
        with transaction.atomic():
            # Make sure a lab day entry is created (additionally to attendance records)
            group_id = Group.objects.only("id").get(name=data["group"]).id
            if group_id is not None:
                LabDay.objects.get_or_create(
                    group_id=group_id,
                    date=data["date"],
                    defaults={"praktikum_day": data["praktikum_day"]},
                )

            for item in data["records"]:
                record, _created = AttendanceRecord.objects.update_or_create(
                    student_id=item["student_id"],
                    praktikum_day=data["praktikum_day"],
                    defaults={
                        "date": data["date"],
                        "is_present": item["is_present"],
                        "comment": item.get("comment"),
                    },
                )
                saved_records.append(record)

        return Response(
            AttendanceRecordSerializer(saved_records, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class AttendanceRecordBulkDeleteView(APIView):
    """Delete all attendance records for a group on a given date"""

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        date_param = request.query_params.get("date")
        if not date_param:
            raise ValidationError({"date": "This query parameter is required."})

        parsed_date = parse_date(date_param)
        if parsed_date is None:
            raise ValidationError({"date": "Enter a valid date (YYYY-MM-DD)."})

        group_param = request.query_params.get("group")
        if not group_param:
            raise ValidationError({"group": "This query parameter is required."})

        group = self._resolve_group(request.user, group_param)

        queryset = AttendanceRecord.objects.filter(
            date=parsed_date,
            student__group=group,
        )
        deleted_count, _ = queryset.delete()

        # delete lab day entry
        LabDay.objects.filter(group=group, date=parsed_date).delete()

        return Response({"deleted": deleted_count}, status=status.HTTP_200_OK)

    def _resolve_group(self, user, group_param: str) -> Group:
        group = self._get_group_by_param(group_param)
        if user.is_superuser:
            return group

        try:
            user_group = user.userprofile.group
        except UserProfile.DoesNotExist:
            raise PermissionDenied("You do not have permission to delete attendance.")

        if group.pk != user_group.pk:
            raise PermissionDenied("You can only delete attendance for your own group.")
        return group

    def _get_group_by_param(self, group_param: str) -> Group:
        try:
            return Group.objects.get(name=group_param)
        except Group.DoesNotExist:
            raise ValidationError({"group": "Group not found."})


class ExperimentList(generics.ListCreateAPIView):
    queryset = Experiment.objects.all()
    serializer_class = ExperimentSerializer

    def get_queryset(self):
        lab_day = self.request.query_params.get("lab_day")
        if lab_day:
            return Experiment.objects.filter(lab_day=lab_day)
        return Experiment.objects.all()


class ExperimentDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Experiment.objects.all()
    serializer_class = ExperimentSerializer

    def get_object(self):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only superusers can change experiments.")
        return get_object_or_404(Experiment, pk=self.kwargs.get("pk"))


class PaperSubmissionList(generics.ListCreateAPIView):
    queryset = PaperSubmission.objects.all()
    serializer_class = PaperSubmissionSerializer

    def get_queryset(self):
        lab_day = self.request.query_params.get("lab_day")
        if not lab_day:
            raise ValidationError({"lab_day": "This query parameter is required."})
        try:
            return PaperSubmission.objects.for_user(self.request.user).filter(
                paper__lab_day=lab_day
            )
        except Paper.DoesNotExist:
            raise Http404("Paper not found")


class PaperSubmissionBulkCreateView(APIView):
    """Create or update paper submissions for multiple students on one lab day"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaperSubmissionBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student_ids = [item["student_id"] for item in data["records"]]
        if len(student_ids) != len(set(student_ids)):
            raise ValidationError({"records": "Duplicate student_id in records."})

        try:
            paper = Paper.objects.get(lab_day=data["lab_day"])
        except Paper.DoesNotExist:
            raise ValidationError({"lab_day": "Paper not found."})

        saved_submissions = []
        with transaction.atomic():
            for item in data["records"]:
                submission, _created = PaperSubmission.objects.update_or_create(
                    student_id=item["student_id"],
                    paper=paper,
                    defaults={
                        "submitted": item["submitted"],
                        "submission_date": item.get("submission_date"),
                        "necessary_corrections": item.get("necessary_corrections"),
                        "accepted": item.get("accepted", False),
                        "accepted_date": item.get("accepted_date"),
                        "is_late": item.get("is_late", False),
                    },
                )
                saved_submissions.append(submission)

        return Response(
            PaperSubmissionSerializer(saved_submissions, many=True).data,
            status=status.HTTP_201_CREATED,
        )


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
    serializer_class = FinalResultSerializer

    def get_object(self):
        student_pk = self.kwargs.get("student_pk")

        base_queryset = FinalResult.objects.for_user(self.request.user)

        if student_pk is not None:
            obj = get_object_or_404(base_queryset, student__pk=student_pk)

        else:
            raise Http404("Please provide 'student_pk'.")

        return obj


class StudentCSVUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if "file" not in request.FILES:
            return Response(
                {"detail": "No file provided. Please upload a CSV file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        csv_file = request.FILES["file"]

        if not csv_file.name.lower().endswith(".csv"):
            return Response(
                {"detail": "File must be a CSV file (.csv)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            valid_students = validate_and_parse_csv_file(csv_file)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_count = bulk_import_students(valid_students)

        response_data = {
            "status": "completed",
            "summary": {
                "total_processed": uploaded_count,
                "successful": uploaded_count,
            },
        }

        return Response(response_data, status=status.HTTP_201_CREATED)
