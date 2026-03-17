from django.contrib import admin

# Register your models here.
from .models import Department
from .models import Student, Experiment, Paper, Exercise, AttendanceRecord, PaperSubmission, ExerciseCompletion, FinalResult, Group, UserProfile, Department

# Student Admin
# @admin.register(Student)
# class StudentAdmin(admin.ModelAdmin):
#     list_display = ['last_name', 'first_name', 'email', 'matriculation_number']
#     list_filter = ['course']
#     search_fields = ['first_name', 'last_name', 'email', 'matriculation_number']
#     list_per_page = 25


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        'last_name',
        'first_name',
        'email',
        'matriculation_number',
        'group',
        'department',
    ]

    list_editable = ['group']

    list_filter = [
        'course',
        'group',
        'department',
    ]

    search_fields = [
        'first_name',
        'last_name',
        'email',
        'matriculation_number'
    ]

    list_per_page = 25
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(department=request.user.userprofile.department)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "group" and not request.user.is_superuser:
            kwargs["queryset"] = Group.objects.filter(
                students__department=request.user.userprofile.department
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# Experiment Admin
@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = ['order', 'title', 'requires_paper_submission']
    list_editable = ['requires_paper_submission']

# Paper Admin
@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ['experiment', 'order', 'title']
    list_filter = ['experiment']

# Exercise Admin
@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ['order', 'title']

# Attendance Record Admin
@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['student', 'praktikum_day', 'date', 'is_present']
    list_filter = ['is_present', 'praktikum_day']
    search_fields = ['student__first_name', 'student__last_name']
    date_hierarchy = 'date'

# Paper Submission Admin
@admin.register(PaperSubmission)
class PaperSubmissionAdmin(admin.ModelAdmin):
    list_display = ['student', 'paper', 'submitted', 'submission_date']
    list_filter = ['submitted', 'paper__experiment']
    search_fields = ['student__first_name', 'student__last_name']

# Exercise Completion Admin
@admin.register(ExerciseCompletion)
class ExerciseCompletionAdmin(admin.ModelAdmin):
    list_display = ['student', 'partner', 'exercise', 'completed', 'completion_date']
    list_filter = ['completed', 'exercise']

# Final Result Admin
@admin.register(FinalResult)
class FinalResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'status', 'papers_completed', 'exercises_completed', 'graded_at']
    list_filter = ['status']
    search_fields = ['student__first_name', 'student__last_name']

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name"]

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']