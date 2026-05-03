from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.urls import reverse
from .utils.csv_import import CSVRowValidator

# Register your models here.
from .models import Department
from .models import (
    Student,
    Experiment,
    Paper,
    Exercise,
    AttendanceRecord,
    PaperSubmission,
    ExerciseCompletion,
    FinalResult,
    Group,
    UserProfile,
    Department,
)
from .utils.csv_import import validate_and_parse_csv_file, bulk_import_students

# Student Admin
# @admin.register(Student)
# class StudentAdmin(admin.ModelAdmin):
#     list_display = ['last_name', 'first_name', 'email', 'matriculation_number']
#     list_filter = ['course']
#     search_fields = ['first_name', 'last_name', 'email', 'matriculation_number']
#     list_per_page = 25


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "User Profile"


class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)


class StudentAdmin(admin.ModelAdmin):
    list_display = [
        "last_name",
        "first_name",
        "email",
        "matriculation_number",
        "group",
        "department",
    ]

    list_editable = ["group"]

    list_filter = [
        "course",
        "group",
        "department",
    ]

    search_fields = ["first_name", "last_name", "email", "matriculation_number"]

    list_per_page = 25

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(group=request.user.userprofile.group)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "group" and not request.user.is_superuser:
            kwargs["queryset"] = Group.objects.filter(
                students__group=request.user.userprofile.group
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ExperimentAdmin(admin.ModelAdmin):
    list_display = ["order", "title", "requires_paper_submission"]
    list_editable = ["requires_paper_submission"]


class PaperAdmin(admin.ModelAdmin):
    list_display = ["experiment", "order", "title"]
    list_filter = ["experiment"]


class ExerciseAdmin(admin.ModelAdmin):
    list_display = ["order", "title"]


class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ["student", "praktikum_day", "date", "is_present"]
    list_filter = ["is_present", "praktikum_day"]
    search_fields = ["student__first_name", "student__last_name"]
    date_hierarchy = "date"

    def get_queryset(self, request):
        return self.model.objects.for_user(request.user)


class PaperSubmissionAdmin(admin.ModelAdmin):
    list_display = ["student", "paper", "submitted", "submission_date"]
    list_filter = ["submitted", "paper__experiment"]
    search_fields = ["student__first_name", "student__last_name"]

    def get_queryset(self, request):
        return self.model.objects.for_user(request.user)


class ExerciseCompletionAdmin(admin.ModelAdmin):
    list_display = ["student", "partner", "exercise", "completed", "completion_date"]
    list_filter = ["completed", "exercise"]

    def get_queryset(self, request):
        return self.model.objects.for_user(request.user)


class FinalResultAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "status",
        "papers_completed",
        "exercises_completed",
        "graded_at",
    ]
    list_filter = ["status"]
    search_fields = ["student__first_name", "student__last_name"]
    readonly_fields = ["papers_completed", "exercises_completed", "attendance_count"]

    def get_queryset(self, request):
        return self.model.objects.for_user(request.user)


class GroupAdmin(admin.ModelAdmin):
    list_display = ["name"]


class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


class CustomAdminSite(admin.AdminSite):
    site_header = "Attendance Administration"
    site_title = "Attendance Admin"
    index_title = "Welcome"
    index_template = "admin/custom_index.html"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["csv_import_url"] = reverse("admin:import_students_csv")
        return super().index(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-students-csv/",
                import_students_csv_view,
                name="import_students_csv",
            ),
        ]
        return custom_urls + urls


@staff_member_required
def import_students_csv_view(request):
    if request.method == "POST" and "file" in request.FILES:
        csv_file = request.FILES["file"]

        if not csv_file.name.lower().endswith(".csv"):
            messages.error(request, "File must be a CSV file (.csv extension).")
            return redirect("admin:import_students_csv")

        try:
            valid_students = validate_and_parse_csv_file(csv_file)
        except ValueError as e:
            messages.error(request, f"CSV validation failed:\n{str(e)}")
            return redirect("admin:import_students_csv")

        try:
            uploaded_count = bulk_import_students(valid_students)
            messages.success(
                request, f"Successfully imported {uploaded_count} students."
            )
            # make sure to return to the student list page
            return redirect("admin:api_student_changelist")
        except Exception as e:
            messages.error(request, f"Import failed: {str(e)}")
            return redirect("admin:import_students_csv")

    return render(
        request,
        "admin/import_students_csv.html",
        {
            "title": "Import Students from CSV",
            "opts": Student._meta,
            "required_fields": list(CSVRowValidator.REQUIRED_FIELDS),
        },
    )


admin_site = CustomAdminSite(name="attendance_admin")
admin_site.register(Student, StudentAdmin)
admin_site.register(Experiment, ExperimentAdmin)
admin_site.register(Paper, PaperAdmin)
admin_site.register(Exercise, ExerciseAdmin)
admin_site.register(AttendanceRecord, AttendanceRecordAdmin)
admin_site.register(PaperSubmission, PaperSubmissionAdmin)
admin_site.register(ExerciseCompletion, ExerciseCompletionAdmin)
admin_site.register(FinalResult, FinalResultAdmin)
admin_site.register(Group, GroupAdmin)
admin_site.register(Department, DepartmentAdmin)
admin_site.register(User, CustomUserAdmin)
