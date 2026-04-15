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
)
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "last_name"]


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = "__all__"


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


class StudentSerializer(serializers.ModelSerializer):
    group = GroupSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)

    class Meta:
        model = Student
        fields = "__all__"


class ExperimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experiment
        fields = "__all__"


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


class PaperSubmissionSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    paper = PaperSerializer(read_only=True)

    class Meta:
        model = PaperSubmission
        fields = "__all__"


class ExerciseCompletionSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    partner = StudentSerializer(read_only=True)
    exercise = ExerciseSerializer(read_only=True)

    class Meta:
        model = ExerciseCompletion
        fields = "__all__"


class FinalResultSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    graded_by = UserSerializer(read_only=True)

    class Meta:
        model = FinalResult
        fields = "__all__"
