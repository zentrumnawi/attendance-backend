from django.db import models

# Create your models here.
# api/models.py

# api/models.py
#from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class Student(models.Model):
    """Individual student information"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    matriculation_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    course = models.CharField(max_length=100, blank=True)
    semester = models.IntegerField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        
    def __str__(self):
        return f"{self.last_name}, {self.first_name} ({self.email})"
    
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
        ordering = ['order']
        
    def __str__(self):
        return f"{self.order}. {self.title}"


class Paper(models.Model):
    """Individual papers that students submit for experiments"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='papers')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=1)
    
    # Each paper can be submitted by multiple students (tracked through PaperSubmission)
    
    class Meta:
        ordering = ['experiment__order', 'order']
        unique_together = ['experiment', 'order']
        
    def __str__(self):
        return f"{self.experiment.title} - Paper {self.order}: {self.title}"


class Exercise(models.Model):
    """Calculation exercises that students complete"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(help_text="Display order of exercises")
    
    class Meta:
        ordering = ['order']
        
    def __str__(self):
        return f"Exercise {self.order}: {self.title}"


class AttendanceRecord(models.Model):
    """Track attendance for each student on each praktikum day"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    praktikum_day = models.IntegerField(help_text="Day number of the praktikum (1, 2, 3, ...)")
    is_present = models.BooleanField(default=False)
    
    # Optional: time tracking
    check_in_time = models.DateTimeField(blank=True, null=True)
    check_out_time = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['student', 'praktikum_day']  # One record per student per day
        
    def __str__(self):
        status = "Present" if self.is_present else "Absent"
        return f"{self.student.full_name()} - Day {self.praktikum_day}: {status}"


class PaperSubmission(models.Model):
    """Track which papers students have submitted"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='paper_submissions')
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='submissions')
    submitted = models.BooleanField(default=False)
    submission_date = models.DateTimeField(blank=True, null=True)
    
    # Optional: track if submission was late
    is_late = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['student', 'paper']  # One submission record per student per paper
        ordering = ['paper__experiment__order', 'paper__order']
        
    def __str__(self):
        status = "✓" if self.submitted else "✗"
        return f"{self.student.full_name()} - {self.paper}: {status}"


class ExerciseCompletion(models.Model):
    """Track which exercises students have completed"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exercise_completions')
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name='completions')
    completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        unique_together = ['student', 'exercise']  # One completion record per student per exercise
        
    def __str__(self):
        status = "✓" if self.completed else "✗"
        return f"{self.student.full_name()} - {self.exercise}: {status}"


class FinalResult(models.Model):
    """Final pass/fail status for each student"""
    class Status(models.TextChoices):
        PASS = 'PASS', 'Pass'
        FAIL = 'FAIL', 'Fail'
        INCOMPLETE = 'INC', 'Incomplete'
        WITHDRAWN = 'WDR', 'Withdrawn'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='final_result')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.INCOMPLETE)
    
    # Criteria tracking (for transparency in decision)
    papers_completed = models.IntegerField(default=0)
    exercises_completed = models.IntegerField(default=0)
    attendance_count = models.IntegerField(default=0)
    
    # If failed, reason can be stored
    failure_reason = models.TextField(blank=True)
    
    # Grading info
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    graded_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Final results"
        
    def __str__(self):
        return f"{self.student.full_name()} - {self.status}"

