from rest_framework import serializers
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
    ExperimentCompletion,
)
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "last_name"]


class GroupSerializer(serializers.ModelSerializer):
    teaching_assistant = UserSerializer(read_only=True)

    class Meta:
        model = Group
        fields = "__all__"
        read_only_fields = ["teaching_assistant"]


class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["name", "description"]


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    group = GroupSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = "__all__"


class AuthenticatedUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(source="userprofile", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "last_name", "is_superuser", "profile"]


class StudentSerializer(serializers.ModelSerializer):
    group = GroupSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    lab_partner_id = serializers.UUIDField(
        source="lab_partner.id", read_only=True, allow_null=True
    )

    class Meta:
        model = Student
        fields = "__all__"
        read_only_fields = ["lab_partner"]


class StudentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            "first_name",
            "last_name",
            "email",
            "matriculation_number",
            "course",
            "semester",
            "group",
            "department",
        ]


class MinimalStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ["id", "matriculation_number"]


class LabPartnerStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ["id", "first_name", "last_name", "matriculation_number"]


# class MinimalPaperSubmissionSerializer(serializers.ModelSerializer):
#     student = MinimalStudentSerializer(read_only=True)
#     paper = PaperSerializer(read_only=True)

#     class Meta:
#         model = PaperSubmission
#         fields = ["id", "student", "paper", "submitted", "submission_date", "necessary_corrections", "accepted", "accepted_date"]


class ExperimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experiment
        fields = "__all__"


class ExperimentCompletionSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    experiment = ExperimentSerializer(read_only=True)

    class Meta:
        model = ExperimentCompletion
        fields = "__all__"


class ExperimentCompletionBulkItemSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    experiment_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=True
    )


class ExperimentCompletionBulkSerializer(serializers.Serializer):
    records = ExperimentCompletionBulkItemSerializer(many=True, allow_empty=False)
    lab_day = serializers.IntegerField(min_value=1)


class PaperSerializer(serializers.ModelSerializer):
    experiment = ExperimentSerializer(read_only=True)

    class Meta:
        model = Paper
        fields = "__all__"


class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = "__all__"


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = "__all__"


class AttendanceRecordBulkItemSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    is_present = serializers.BooleanField()
    comment = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class AttendanceRecordBulkSerializer(serializers.Serializer):
    date = serializers.DateField()
    day_type = serializers.ChoiceField(
        choices=AttendanceRecord.DayType.choices,
        default=AttendanceRecord.DayType.LAB,
    )
    praktikum_day = serializers.IntegerField(
        min_value=1, required=False, allow_null=True
    )
    group = serializers.CharField(required=False, allow_null=True)
    records = AttendanceRecordBulkItemSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        day_type = attrs.get("day_type", AttendanceRecord.DayType.LAB)
        if day_type == AttendanceRecord.DayType.LAB:
            if not attrs.get("group"):
                raise serializers.ValidationError(
                    {"group": "This field is required for lab attendance."}
                )
            if attrs.get("praktikum_day") is None:
                raise serializers.ValidationError(
                    {"praktikum_day": "This field is required for lab attendance."}
                )
        else:
            attrs["praktikum_day"] = None
        return attrs


class AttendanceSessionPatchSerializer(serializers.Serializer):
    """Move a lab session from one praktikum_day to another (delete + create)."""

    old_praktikum_day = serializers.IntegerField(min_value=1)
    date = serializers.DateField()
    praktikum_day = serializers.IntegerField(min_value=1)
    group = serializers.CharField()
    records = AttendanceRecordBulkItemSerializer(many=True, allow_empty=False)


class PaperSubmissionBulkItemSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    submitted = serializers.BooleanField()
    main_author = serializers.BooleanField(required=False, default=False)
    submission_date = serializers.DateTimeField(required=False, allow_null=True)
    necessary_corrections = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    accepted = serializers.BooleanField(required=False, default=False)
    accepted_date = serializers.DateTimeField(required=False, allow_null=True)
    is_late = serializers.BooleanField(required=False, default=False)


class PaperSubmissionBulkSerializer(serializers.Serializer):
    lab_day = serializers.IntegerField(min_value=1)
    records = PaperSubmissionBulkItemSerializer(many=True, allow_empty=False)


class PaperSubmissionSerializer(serializers.ModelSerializer):
    student = MinimalStudentSerializer(read_only=True)
    paper = PaperSerializer(read_only=True)

    class Meta:
        model = PaperSubmission
        fields = "__all__"


class ExerciseCompletionSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    exercise = ExerciseSerializer(read_only=True)

    class Meta:
        model = ExerciseCompletion
        fields = "__all__"


class ExerciseCompletionUpsertSerializer(serializers.Serializer):
    lab_day = serializers.IntegerField(min_value=1)
    student_id = serializers.UUIDField()
    completed = serializers.BooleanField()


class LabPartnershipPairSerializer(serializers.Serializer):
    student_a_id = serializers.UUIDField()
    student_b_id = serializers.UUIDField()


class LabPartnershipBulkSerializer(serializers.Serializer):
    group = serializers.CharField()
    pairs = LabPartnershipPairSerializer(many=True, allow_empty=True)
    unpaired_student_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=True
    )


class LabPartnerDetailSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    partner = LabPartnerStudentSerializer(allow_null=True)


class FinalResultSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    graded_by = UserSerializer(read_only=True)
    papers_completed = serializers.IntegerField(read_only=True)
    exercises_completed = serializers.IntegerField(read_only=True)
    experiments_completed = serializers.IntegerField(read_only=True)
    lab_attendance_count = serializers.IntegerField(read_only=True)
    lecture_attendance_count = serializers.IntegerField(read_only=True)
    attendance_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = FinalResult
        fields = "__all__"
