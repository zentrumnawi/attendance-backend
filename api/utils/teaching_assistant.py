from django.db import transaction


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
