from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AttendanceRecord, FinalResult, LabDay, Student


@receiver(post_save, sender=Student)
def create_final_result_for_new_student(
    sender, instance: Student, created: bool, **kwargs
):
    # return if student is not created, but modified
    if not created:
        return

    FinalResult.objects.get_or_create(student=instance)


@receiver(post_save, sender=AttendanceRecord)
def ensure_lab_day_for_attendance_record(sender, instance: AttendanceRecord, **kwargs):
    if instance.day_type != AttendanceRecord.DayType.LAB:
        return
    if instance.student.group_id is None or instance.praktikum_day is None:
        return

    LabDay.objects.update_or_create(
        group_id=instance.student.group_id,
        praktikum_day=instance.praktikum_day,
        defaults={"date": instance.date},
    )
