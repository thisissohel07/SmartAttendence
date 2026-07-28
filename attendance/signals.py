import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CampusConfig

logger = logging.getLogger(__name__)

# Ensure at least one default CampusConfig exists
@receiver(post_save, sender=CampusConfig)
def campus_config_saved(sender, instance, **kwargs):
    logger.info(f"Campus configuration updated: {instance}")
