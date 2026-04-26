from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Invoice, Load, LoadStatusHistory


@receiver(pre_save, sender=Load)
def track_previous_load_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return

    previous = sender.objects.filter(pk=instance.pk).values('status').first()
    instance._previous_status = previous.get('status') if previous else None


@receiver(post_save, sender=Load)
def create_invoice_on_load_completed(sender, instance, created, **kwargs):
    previous_status = getattr(instance, '_previous_status', None)
    became_completed = instance.status == 'Completed' and (created or previous_status != 'Completed')
    if not became_completed:
        return

    if instance.user is None or instance.user.role != 'sme':
        return

    if Invoice.objects.filter(load=instance).exists():
        return

    route = f"{instance.pickup_location or ''} -> {instance.drop_location or ''}".strip(" ->")

    Invoice.objects.create(
        load=instance,
        sme=instance.user,
        driver=instance.driver,
        route=route or None,
        cost=instance.budget_rate,
        paid=False,
        payment_status="unpaid",
        payment_method="cash",
    )


@receiver(post_save, sender=Load)
def create_load_status_history(sender, instance, created, **kwargs):
    previous_status = getattr(instance, '_previous_status', None)
    status_changed = created or previous_status != instance.status
    if not status_changed or not instance.status:
        return

    location = None
    if instance.driver_current_latitude is not None and instance.driver_current_longitude is not None:
        location = f"{instance.driver_current_latitude},{instance.driver_current_longitude}"

    LoadStatusHistory.objects.create(
        load=instance,
        status=instance.status,
        location=location,
    )
