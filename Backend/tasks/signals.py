from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import UserProfile
import logging
logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    logger.info(f"Señal post_save para User recibida. Created: {created}")
    logger.info(f"Tipo de instance: {type(instance)}")
    logger.info(f"Valor de instance: {instance}")
    if created:
        try:
            UserProfile.objects.create(user=instance)
            logger.info(f"UserProfile creado para el usuario: {instance.username}")
        except Exception as e:
            logger.error(f"Error al crear UserProfile: {e}")
