from django.db import transaction
from api.models import Group


@transaction.atomic
def sync_teaching_assistant_for_user_profile(profile, old_group_id, new_group_id):
    """Keep Group.teaching_assistant aligned when a UserProfile's group changes."""
    if old_group_id == new_group_id:
        return

    if not new_group_id:
        return

    group = profile.group
    if group.teaching_assistant_id != profile.user_id:
        group.teaching_assistant = profile.user
        group.save(update_fields=["teaching_assistant"])

    if old_group_id:
        old_group = Group.objects.get(id=old_group_id)
        if old_group.teaching_assistant_id == profile.user_id:
            old_group.teaching_assistant = None
            old_group.save(update_fields=["teaching_assistant"])
