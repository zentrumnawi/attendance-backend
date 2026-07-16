from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
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
    ExperimentCompletion,
    Paper,
    Exercise,
    UserProfile,
    User,
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
    ExerciseCompletionUpsertSerializer,
    FinalResultSerializer,
    GroupSerializer,
    DepartmentSerializer,
    ExperimentSerializer,
    PaperSerializer,
    ExerciseSerializer,
    UserProfileSerializer,
    ExperimentCompletionBulkSerializer,
    ExperimentCompletionSerializer,
    LabPartnershipBulkSerializer,
    LabPartnerDetailSerializer,
    UserSerializer,
    GroupCreateSerializer,
    StudentUpdateSerializer,
)

from .utils.csv_import import validate_and_parse_csv_file, bulk_import_students
from .utils.lab_partner import (
    clear_group_lab_partners,
    clear_student_lab_partner,
    pair_lab_partners,
)


def _allowed_student_ids(user, student_ids):
    return set(
        Student.objects.for_user(user)
        .filter(pk__in=student_ids)
        .values_list("pk", flat=True)
    )


def _resolve_group_param(user, group_param: str) -> Group:
    try:
        group = Group.objects.get(name=group_param)
    except Group.DoesNotExist:
        try:
            group = Group.objects.get(pk=group_param)
        except (Group.DoesNotExist, ValueError, ValidationError):
            raise ValidationError({"group": "Group not found."})
    return group


def _lab_partnership_response_for_group(group):
    students = Student.objects.filter(group=group).order_by("last_name", "first_name")
    return [
        {
            "student_id": student.id,
            "partner_id": student.lab_partner_id,
        }
        for student in students
    ]


class StudentList(generics.ListCreateAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

    def get_queryset(self):
        return Student.objects.for_user(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = StudentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = serializer.save()
        return Response(
            StudentSerializer(student).data,
            status=status.HTTP_201_CREATED,
        )


class StudentDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return StudentUpdateSerializer
        return StudentSerializer

    def get_object(self):
        return get_object_or_404(
            Student.objects.for_user(self.request.user),
            pk=self.kwargs.get("pk"),
        )


# Get attendance records (according to permissions): in toto, by date or by student
class AttendanceRecordList(generics.ListCreateAPIView):
    queryset = AttendanceRecord.objects.all()
    serializer_class = AttendanceRecordSerializer

    def get_queryset(self):
        queryset = AttendanceRecord.objects.for_user(self.request.user)
        date_param = self.request.query_params.get("date")
        student_pk = self.request.query_params.get("student_pk")
        day_type = self.request.query_params.get("day_type")
        group_param = self.request.query_params.get("group")
        praktikum_day_param = self.request.query_params.get("praktikum_day")

        if date_param:
            parsed_date = parse_date(date_param)
            if parsed_date:
                queryset = queryset.filter(date=parsed_date)

        if student_pk:
            queryset = queryset.filter(student__pk=student_pk)

        if day_type:
            queryset = queryset.filter(day_type=day_type)

        if praktikum_day_param is not None:
            try:
                queryset = queryset.filter(praktikum_day=int(praktikum_day_param))
            except (TypeError, ValueError):
                raise ValidationError(
                    {"praktikum_day": "Enter a valid integer."}
                )

        if group_param:
            group = _resolve_group_param(self.request.user, group_param)
            queryset = queryset.filter(student__group=group)

        return queryset


# get single attendance record
class AttendanceRecordDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AttendanceRecordSerializer

    def get_object(self):
        student_pk = self.kwargs.get("student_pk")
        base_queryset = AttendanceRecord.objects.for_user(self.request.user)

        praktikum_day = self.kwargs.get("praktikum_day")
        if praktikum_day is not None:
            return get_object_or_404(
                base_queryset,
                student__pk=student_pk,
                praktikum_day=praktikum_day,
                day_type=AttendanceRecord.DayType.LAB,
            )

        session_date = parse_date(self.kwargs.get("session_date"))
        if student_pk and session_date is not None:
            return get_object_or_404(
                base_queryset,
                student__pk=student_pk,
                date=session_date,
                day_type=AttendanceRecord.DayType.LECTURE,
            )

        raise Http404(
            "Provide student_pk with praktikum_day (lab) or a valid session date (lecture)."
        )


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
        day_type = data.get("day_type", AttendanceRecord.DayType.LAB)

        # check for duplicate student_id in records
        student_ids = [item["student_id"] for item in data["records"]]
        if len(student_ids) != len(set(student_ids)):
            raise ValidationError({"records": "Duplicate student_id in records."})

        group = None
        if day_type == AttendanceRecord.DayType.LAB:
            group = self._resolve_group(request.user, data["group"])
            self._validate_students_in_group(group, student_ids)
        else:
            self._validate_students_for_user(request.user, student_ids)

        saved_records = []
        with transaction.atomic():
            if day_type == AttendanceRecord.DayType.LAB:
                LabDay.objects.update_or_create(
                    group=group,
                    praktikum_day=data["praktikum_day"],
                    defaults={"date": data["date"]},
                )

            for item in data["records"]:
                if day_type == AttendanceRecord.DayType.LAB:
                    record, _created = AttendanceRecord.objects.update_or_create(
                        student_id=item["student_id"],
                        praktikum_day=data["praktikum_day"],
                        day_type=AttendanceRecord.DayType.LAB,
                        defaults={
                            "date": data["date"],
                            "is_present": item["is_present"],
                            "comment": item.get("comment"),
                        },
                    )
                else:
                    record, _created = AttendanceRecord.objects.update_or_create(
                        student_id=item["student_id"],
                        date=data["date"],
                        day_type=AttendanceRecord.DayType.LECTURE,
                        defaults={
                            "is_present": item["is_present"],
                            "comment": item.get("comment"),
                            "praktikum_day": None,
                        },
                    )
                saved_records.append(record)

        return Response(
            AttendanceRecordSerializer(saved_records, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    def _get_group_by_param(self, group_param: str) -> Group:
        try:
            return Group.objects.get(name=group_param)
        except Group.DoesNotExist:
            try:
                return Group.objects.get(pk=group_param)
            except (Group.DoesNotExist, ValueError, ValidationError):
                raise ValidationError({"group": "Group not found."})

    def _resolve_group(self, user, group_param: str) -> Group:
        group = self._get_group_by_param(group_param)
        if user.is_superuser:
            return group

        try:
            user_group = user.userprofile.group
        except UserProfile.DoesNotExist:
            raise PermissionDenied("You do not have permission to manage attendance.")

        if group.pk != user_group.pk:
            raise PermissionDenied("You can only manage attendance for your own group.")
        return group

    def _validate_students_in_group(self, group: Group, student_ids):
        in_group_count = Student.objects.filter(pk__in=student_ids, group=group).count()
        if in_group_count != len(student_ids):
            raise ValidationError(
                {
                    "records": "One or more students do not belong to the specified group."
                }
            )

    def _validate_students_for_user(self, user, student_ids):
        allowed_ids = _allowed_student_ids(user, student_ids)
        if len(allowed_ids) != len(student_ids):
            raise ValidationError(
                {"records": "One or more students are outside your group."}
            )


class AttendanceRecordBulkDeleteView(APIView):
    """Delete all attendance records for a roll-call session"""

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        day_type = request.query_params.get("day_type", AttendanceRecord.DayType.LAB)
        if day_type not in AttendanceRecord.DayType.values:
            raise ValidationError({"day_type": "Enter LAB or LECTURE."})

        if day_type == AttendanceRecord.DayType.LECTURE:
            date_param = request.query_params.get("date")
            if not date_param:
                raise ValidationError({"date": "This query parameter is required."})

            parsed_date = parse_date(date_param)
            if parsed_date is None:
                raise ValidationError({"date": "Enter a valid date (YYYY-MM-DD)."})

            queryset = AttendanceRecord.objects.filter(
                date=parsed_date,
                day_type=AttendanceRecord.DayType.LECTURE,
            )
            queryset = self._scope_to_user_group(request.user, queryset)
            deleted_count, _ = queryset.delete()
            return Response({"deleted": deleted_count}, status=status.HTTP_200_OK)

        praktikum_day_param = request.query_params.get("praktikum_day")
        if not praktikum_day_param:
            raise ValidationError(
                {"praktikum_day": "This query parameter is required."}
            )
        try:
            praktikum_day = int(praktikum_day_param)
        except (TypeError, ValueError):
            raise ValidationError({"praktikum_day": "Enter a valid integer."})

        group_param = request.query_params.get("group")
        if not group_param:
            raise ValidationError({"group": "This query parameter is required."})

        group = self._resolve_group(request.user, group_param)

        queryset = AttendanceRecord.objects.filter(
            praktikum_day=praktikum_day,
            student__group=group,
            day_type=AttendanceRecord.DayType.LAB,
        )
        deleted_count, _ = queryset.delete()

        LabDay.objects.filter(group=group, praktikum_day=praktikum_day).delete()

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
            try:
                return Group.objects.get(pk=group_param)
            except (Group.DoesNotExist, ValueError, ValidationError):
                raise ValidationError({"group": "Group not found."})

    def _scope_to_user_group(self, user, queryset):
        if user.is_superuser:
            return queryset
        try:
            user_group = user.userprofile.group
        except UserProfile.DoesNotExist:
            raise PermissionDenied("You do not have permission to delete attendance.")
        return queryset.filter(student__group=user_group)


class GroupList(generics.ListCreateAPIView):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer

    def get_queryset(self):
        return Group.objects.all()

    def create(self, request, *args, **kwargs):
        serializer = GroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = serializer.save()
        return Response(
            GroupSerializer(group).data,
            status=status.HTTP_201_CREATED,
        )


class GroupDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return GroupCreateSerializer
        return GroupSerializer

    def get_object(self):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only superusers can change groups.")
        return get_object_or_404(Group, pk=self.kwargs.get("pk"))


class ExerciseList(generics.ListCreateAPIView):
    queryset = Exercise.objects.all()
    serializer_class = ExerciseSerializer

    def get_queryset(self):
        return Exercise.objects.all()


class ExerciseDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Exercise.objects.all()
    serializer_class = ExerciseSerializer

    def get_object(self):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only superusers can change exercises.")
        return get_object_or_404(Exercise, pk=self.kwargs.get("pk"))


class UserList(generics.ListCreateAPIView):
    queryset = User.objects.filter(is_superuser=False)
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(is_superuser=False)


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


class ExperimentCompletionPerStudent(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Student.objects.for_user(request.user)

        lab_day = request.query_params.get("lab_day")
        if not lab_day:
            raise ValidationError({"lab_day": "This query parameter is required."})

        experiments = Experiment.objects.filter(lab_day=lab_day)
        if not experiments:
            raise ValidationError({"lab_day": "This lab day does not exist."})

        experiment_completions = []

        for student in queryset:
            experiment_completions.append(
                {
                    "student": student.id,
                    "experiment_completions": student.experiment_completions.filter(
                        completed=True, experiment__in=experiments
                    ).values_list("experiment_id", flat=True),
                }
            )

        return Response(experiment_completions, status=status.HTTP_200_OK)


class ExerciseCompletionStatus(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Student.objects.for_user(request.user)

        lab_day = request.query_params.get("lab_day")
        if not lab_day:
            raise ValidationError({"lab_day": "This query parameter is required."})

        exercises = Exercise.objects.filter(lab_day=lab_day)
        if not exercises:
            raise ValidationError({"lab_day": "This lab day does not exist."})

        student_ids = ExerciseCompletion.objects.filter(
            completed=True, exercise__in=exercises
        ).values_list("student__id", flat=True)

        return Response(student_ids, status=status.HTTP_200_OK)


class ExperimentCompletionBulkCreateOrUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ExperimentCompletionBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student_ids = [item["student_id"] for item in data["records"]]

        experiments_for_day = Experiment.objects.filter(lab_day=data["lab_day"])
        if not experiments_for_day.exists():
            raise ValidationError({"lab_day": "This lab day does not exist."})

        lab_day_experiment_ids = set(experiments_for_day.values_list("pk", flat=True))

        saved_completions = []
        with transaction.atomic():
            for item in data["records"]:
                completed_experiment_ids = set(item["experiment_ids"])
                for experiment in experiments_for_day:
                    if experiment.id in completed_experiment_ids:
                        completion, _created = (
                            ExperimentCompletion.objects.update_or_create(
                                student_id=item["student_id"],
                                experiment_id=experiment.id,
                                defaults={
                                    "completed": True,
                                    "completion_date": timezone.now(),
                                },
                            )
                        )
                    else:
                        completion, _created = (
                            ExperimentCompletion.objects.update_or_create(
                                student_id=item["student_id"],
                                experiment_id=experiment.id,
                                defaults={
                                    "completed": False,
                                    "completion_date": None,
                                },
                            )
                        )
                    saved_completions.append(completion)

        return Response(
            ExperimentCompletionSerializer(saved_completions, many=True).data,
            status=status.HTTP_201_CREATED,
        )


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


class ExerciseCompletionUpsertView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ExerciseCompletionUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student_id = data["student_id"]
        if student_id not in _allowed_student_ids(request.user, [student_id]):
            raise PermissionDenied("You do not have permission to modify this student.")

        try:
            exercise = Exercise.objects.get(lab_day=data["lab_day"])
        except Exercise.DoesNotExist:
            raise ValidationError({"lab_day": "Exercise not found."})

        completion, _created = ExerciseCompletion.objects.update_or_create(
            student_id=student_id,
            exercise=exercise,
            defaults={
                "completed": data["completed"],
                "completion_date": timezone.now() if data["completed"] else None,
            },
        )

        return Response(
            ExerciseCompletionSerializer(completion).data,
            status=status.HTTP_201_CREATED,
        )


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


class LabPartnershipPerStudentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        group_param = request.query_params.get("group")
        if request.user.is_superuser:
            if not group_param:
                raise ValidationError({"group": "This query parameter is required."})
            group = Group.objects.get(name=group_param)
        else:
            try:
                group = request.user.userprofile.group.name
            except UserProfile.DoesNotExist:
                raise PermissionDenied(
                    "You do not have permission to view lab partnerships."
                )

        return Response(
            _lab_partnership_response_for_group(group), status=status.HTTP_200_OK
        )

    def delete(self, request):
        student_id = request.query_params.get("student_id")
        if not student_id:
            raise ValidationError({"student_id": "This query parameter is required."})

        student = get_object_or_404(
            Student.objects.for_user(request.user), pk=student_id
        )
        deleted = clear_student_lab_partner(student)
        return Response({"deleted": 1 if deleted else 0}, status=status.HTTP_200_OK)


class LabPartnershipBulkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LabPartnershipBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        group = Group.objects.get(name=data["group"])
        group_student_ids = set(
            Student.objects.filter(group=group).values_list("pk", flat=True)
        )

        # Collect every student ID referenced in the payload
        # mentioned_student_ids (set): unique IDs — used for coverage and permission checks
        # all_mentioned_ids (list): every occurrence — used to detect duplicates
        mentioned_student_ids = set(data["unpaired_student_ids"])
        all_mentioned_ids = list(data["unpaired_student_ids"])
        for pair in data["pairs"]:
            if pair["student_a_id"] == pair["student_b_id"]:
                raise ValidationError(
                    {"pairs": "A student cannot be paired with themselves."}
                )
            all_mentioned_ids.extend([pair["student_a_id"], pair["student_b_id"]])
            mentioned_student_ids.add(pair["student_a_id"])
            mentioned_student_ids.add(pair["student_b_id"])

        # Reject if a student appears in more than one pair or in both a pair and unpaired list
        if len(all_mentioned_ids) != len(set(all_mentioned_ids)):
            raise ValidationError(
                {
                    "records": "Each student may appear in only one pair or unpaired list."
                }
            )

        # Bulk replace requires a complete snapshot: every group member must be included.
        if mentioned_student_ids != group_student_ids:
            raise ValidationError(
                {
                    "records": (
                        "Every student in the group must appear in exactly one pair "
                        "or in unpaired_student_ids."
                    )
                }
            )

        allowed_ids = _allowed_student_ids(request.user, mentioned_student_ids)
        if allowed_ids != mentioned_student_ids:
            raise PermissionDenied(
                "You do not have permission to modify these students."
            )

        students_by_id = {
            student.id: student
            for student in Student.objects.filter(pk__in=mentioned_student_ids)
        }

        with transaction.atomic():
            # first clear all lab partnerships, then reset pairs
            clear_group_lab_partners(group)
            for pair in data["pairs"]:
                student_a = students_by_id[pair["student_a_id"]]
                student_b = students_by_id[pair["student_b_id"]]
                pair_lab_partners(student_a, student_b)

        return Response(
            _lab_partnership_response_for_group(group),
            status=status.HTTP_201_CREATED,
        )


class StudentLabPartnerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        student = get_object_or_404(
            Student.objects.for_user(request.user).select_related("lab_partner"),
            pk=pk,
        )

        return Response(
            LabPartnerDetailSerializer(
                {"student_id": student.id, "partner": student.lab_partner}
            ).data,
            status=status.HTTP_200_OK,
        )


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
