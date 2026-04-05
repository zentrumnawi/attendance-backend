from django.db import models

# Create your models here.
# api/models.py

# api/models.py
# from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
import uuid


class Department(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Group(models.Model):
    """Group of students (lab group, practical group, etc.)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class GroupRestrictedManager(models.Manager):
    def for_user(self, user):
        if user.is_superuser:
            return self.get_queryset()
        try:
            user_group = user.userprofile.group
            return self.get_queryset().filter(student__group=user_group)
        except UserProfile.DoesNotExist:
            return self.none()


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.PROTECT)

    def __str__(self):
        return self.user.username


class Student(models.Model):
    """Individual student information"""

    objects = GroupRestrictedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    matriculation_number = models.CharField(
        max_length=20, unique=True, blank=True, null=True
    )
    course = models.CharField(max_length=100, blank=True)
    semester = models.IntegerField(blank=True, null=True)

    group = models.ForeignKey(
        Group, on_delete=models.SET_NULL, null=True, blank=True, related_name="students"
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="students",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.last_name}, {self.first_name} ({self.matriculation_number})"

    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Experiment(models.Model):
    """Experiments that students need to complete"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(help_text="Display order of experiments")

    # Each experiment can have multiple papers
    requires_paper_submission = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.order}. {self.title}"


class Paper(models.Model):
    """Individual papers that students submit for experiments"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    experiment = models.ForeignKey(
        Experiment, on_delete=models.CASCADE, related_name="papers"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=1)

    # Each paper can be submitted by multiple students (tracked through PaperSubmission)

    class Meta:
        ordering = ["experiment__order", "order"]
        unique_together = ["experiment", "order"]

    def __str__(self):
        return f"{self.experiment.title} - Paper {self.order}: {self.title}"


class Exercise(models.Model):
    """Calculation exercises that students complete"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(help_text="Display order of exercises")

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Exercise {self.order}: {self.title}"


class AttendanceRecord(models.Model):
    """Track attendance for each student on each praktikum day"""

    objects = GroupRestrictedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attendance_records"
    )
    date = models.DateField()
    praktikum_day = models.IntegerField(
        help_text="Day number of the praktikum (1, 2, 3, ...)"
    )
    is_present = models.BooleanField(default=False)
    comment = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ["student", "praktikum_day"]  # One record per student per day

    def __str__(self):
        status = "1" if self.is_present else "0"

        return f"{self.student.full_name()} - Day {self.praktikum_day}: {status}"


class PaperSubmission(models.Model):
    """Track which papers students have submitted"""

    objects = GroupRestrictedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="paper_submissions"
    )
    paper = models.ForeignKey(
        Paper, on_delete=models.CASCADE, related_name="submissions"
    )
    submitted = models.BooleanField(default=False)
    submission_date = models.DateTimeField(blank=True, null=True)

    # Optional: track if submission was late
    is_late = models.BooleanField(default=False)

    class Meta:
        unique_together = [
            "student",
            "paper",
        ]  # One submission record per student per paper
        ordering = ["paper__experiment__order", "paper__order"]

    def __str__(self):
        status = "1" if self.submitted else "0"
        return f"{self.student.full_name()} - {self.paper}: {status}"


class ExerciseCompletion(models.Model):
    """Track which exercises students have completed"""

    objects = GroupRestrictedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="exercise_completions"
    )

    partner = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exercise_partnerships",
    )

    exercise = models.ForeignKey(
        Exercise, on_delete=models.CASCADE, related_name="completions"
    )

    completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = [
            "student",
            "exercise",
        ]  # One completion record per student per exercise

    def __str__(self):
        status = "1" if self.completed else "0"
        partner_name = self.partner.full_name() if self.partner else "None"
        return (
            f"{self.student.full_name()} - {self.exercise} ({partner_name}): {status}"
        )

    def clean(self):
        if self.partner and self.student == self.partner:
            raise ValidationError("Student cannot be their own partner.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class FinalResult(models.Model):
    """Final pass/fail status for each student"""

    objects = GroupRestrictedManager()

    class Status(models.TextChoices):
        PASS = "PASS", "Pass"
        FAIL = "FAIL", "Fail"
        INCOMPLETE = "INC", "Incomplete"
        WITHDRAWN = "WDR", "Withdrawn"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(
        Student, on_delete=models.CASCADE, related_name="final_result"
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.INCOMPLETE
    )

    # Criteria tracking (for transparency in decision)
    papers_completed = models.IntegerField(default=0)
    exercises_completed = models.IntegerField(default=0)
    attendance_count = models.IntegerField(default=0)

    # If failed, reason can be stored
    failure_reason = models.TextField(blank=True)

    # Grading info
    graded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    graded_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Final results"

    def __str__(self):
        return f"{self.student.full_name()} - {self.status}"
