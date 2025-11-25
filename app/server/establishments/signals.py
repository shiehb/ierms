from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Establishment
from audit.utils import log_activity

@receiver(post_save, sender=Establishment)
def log_establishment_save(sender, instance, created, **kwargs):
    user = getattr(instance, "_action_user", None)  # set in views before saving

    if created:
        log_activity(
            user,
            "create",
            module="ESTABLISHMENTS",
            description=f"Created establishment: {instance.name}",
        )
    else:
        log_activity(
            user,
            "update",
            module="ESTABLISHMENTS",
            description=f"Updated establishment: {instance.name}",
        )
