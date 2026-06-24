from django.core.exceptions import ValidationError
from django.db import transaction

from api.models import Student


def clear_student_lab_partner(student):
    student.refresh_from_db()
    if not student.lab_partner_id:
        return False

    partner = student.lab_partner
    student.lab_partner = None
    student.save(update_fields=["lab_partner", "updated_at"])

    partner.refresh_from_db()
    if partner.lab_partner_id == student.pk:
        partner.lab_partner = None
        partner.save(update_fields=["lab_partner", "updated_at"])

    return True


def set_lab_partner(student, partner):
    with transaction.atomic():
        if partner is None:
            return clear_student_lab_partner(student)

        if student.pk == partner.pk:
            raise ValidationError("A student cannot be their own lab partner.")
        if student.group_id != partner.group_id:
            raise ValidationError("Lab partners must belong to the same group.")

        clear_student_lab_partner(student)
        clear_student_lab_partner(partner)

        student.lab_partner = partner
        partner.lab_partner = student
        student.save(update_fields=["lab_partner", "updated_at"])
        partner.save(update_fields=["lab_partner", "updated_at"])

    return True


def clear_group_lab_partners(group):
    Student.objects.filter(group=group).update(lab_partner=None)


def pair_lab_partners(student_a, student_b):
    if student_a.group_id != student_b.group_id:
        raise ValidationError("Lab partners must belong to the same group.")
    if student_a.pk == student_b.pk:
        raise ValidationError("A student cannot be their own lab partner.")

    student_a.lab_partner = student_b
    student_b.lab_partner = student_a
    student_a.save(update_fields=["lab_partner", "updated_at"])
    student_b.save(update_fields=["lab_partner", "updated_at"])
