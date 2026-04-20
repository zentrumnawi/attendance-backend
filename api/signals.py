from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import FinalResult, Student


@receiver(post_save, sender=Student)
def create_final_result_for_new_student(
    sender, instance: Student, created: bool, **kwargs
):
    # return if student is not created, but modified
    if not created:
        return

    FinalResult.objects.get_or_create(student=instance)
