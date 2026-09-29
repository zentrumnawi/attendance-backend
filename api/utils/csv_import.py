import csv
import io
from typing import List, Tuple, Dict, Any
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from ..models import Student, Group, FinalResult


class CSVRowValidator:
    """Validates and parses a single CSV row into a Student instance."""

    # TODO: adjust to real structure of csv files
    REQUIRED_FIELDS = {
        "first_name",
        "last_name",
        "email",
        "matriculation_number",
        "group",
    }

    def __init__(self, row: Dict[str, str], row_number: int):
        self.row = {
            k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()
        }
        self.row_number = row_number
        self.errors = {}

    def validate(self) -> Tuple[bool, Dict[str, Any]]:
        self._validate_required_fields()
        self._validate_email()
        group = self._resolve_group()

        if self.errors:
            return False, self.errors

        # Check for fields that would identify existing students
        email = self.row.get("email", "").strip()
        matriculation_number = self.row.get("matriculation_number", "").strip() or None
        # Try to find an existing student
        student = None
        if email:
            try:
                student = Student.objects.get(email=email)
            except Student.DoesNotExist:
                pass

        if not student and matriculation_number:
            try:
                student = Student.objects.get(matriculation_number=matriculation_number)
            except Student.DoesNotExist:
                pass
        if student:
            # If student exists, update its fields
            student.first_name = self.row.get("first_name", "").strip()
            student.last_name = self.row.get("last_name", "").strip()
            student.group = group
            student.email = email
            student.matriculation_number = matriculation_number

            try:
                student.full_clean()
                student.save()
                return True, {"action": "updated", "student_id": student.id}
            except ValidationError as e:
                # Handle validation errors during update
                if hasattr(e, "error_dict"):
                    for field, field_errors in e.error_dict.items():
                        self.errors[field] = str(field_errors[0])
                else:
                    self.errors["__all__"] = str(e)
                return False, self.errors

        # If no existing student found, create a new one (but don't save yet)
        try:
            new_student = Student(
                first_name=self.row.get("first_name", "").strip(),
                last_name=self.row.get("last_name", "").strip(),
                email=email,
                matriculation_number=matriculation_number,
                group=group,
            )
            new_student.full_clean()
            return True, {"action": "created", "student": new_student}

        except ValidationError as e:
            # check for field-specific errors
            if hasattr(e, "error_dict"):
                for field, field_errors in e.error_dict.items():
                    self.errors[field] = str(field_errors[0])
            else:
                self.errors["__all__"] = str(e)
            return False, self.errors

    def _validate_required_fields(self):
        for field in self.REQUIRED_FIELDS:
            if field not in self.row:
                self.errors[field] = f"Missing required column: {field}"

    def _validate_email(self):
        if "email" in self.errors:
            return

        email = self.row.get("email", "").strip()
        if not email:
            self.errors["email"] = "Email is required"
            return

        try:
            validate_email(email)
        except ValidationError:
            self.errors["email"] = "Invalid email format"

    # we assume admin has already created the groups previously
    def _resolve_group(self) -> Group | None:
        """Resolve group name to Group instance. Returns None if group column is empty."""
        group_name = self.row.get("group", "").strip()
        if not group_name:
            return None

        try:
            group = Group.objects.get(name__iexact=group_name)
            return group
        except Group.DoesNotExist:
            self.errors["group"] = f"Group '{group_name}' not found"
            return None


def validate_and_parse_csv_file(
    csv_file,
) -> List[Student]:
    new_students_for_bulk_create = []
    errors = []

    try:
        # make sure pointer is at the beginning of the file
        csv_file.seek(0)
        decoded_file = csv_file.read().decode("utf-8")
        # make iterable
        csv_reader = csv.DictReader(io.StringIO(decoded_file))

        if not csv_reader.fieldnames:
            raise ValueError("CSV file is empty or has no headers")

        for row_number, row in enumerate(csv_reader, start=2):
            validator = CSVRowValidator(row, row_number)
            # contains either False and error details or True and student instance
            is_valid, result = validator.validate()

            if not is_valid:
                error_details = ", ".join(
                    f"{field}: {msg}" for field, msg in result.items()
                )
                errors.append(f"Row {row_number}: {error_details}")
                continue

            if result.get("action") == "created":
                new_students_for_bulk_create.append(result["student"])

    except UnicodeDecodeError:
        raise ValueError("CSV file must be UTF-8 encoded")
    except Exception as e:
        raise ValueError(f"Error parsing CSV file: {str(e)}")

    if errors:
        raise ValueError("Validation errors:\n" + "\n".join(errors))

    return new_students_for_bulk_create


def bulk_import_students(valid_students: List[Student]) -> int:
    if not valid_students:
        return 0

    with transaction.atomic():
        created = Student.objects.bulk_create(valid_students)
        FinalResult.objects.bulk_create(
            [FinalResult(student=student) for student in created]
        )
    return len(created)
