from django.db import migrations


def pending_to_unpaid(apps, schema_editor):
    BillingRecord = apps.get_model('inspections', 'BillingRecord')
    BillingRecord.objects.filter(payment_status='PENDING').update(payment_status='UNPAID')


def unpaid_to_pending(apps, schema_editor):
    BillingRecord = apps.get_model('inspections', 'BillingRecord')
    BillingRecord.objects.filter(payment_status='UNPAID').update(payment_status='PENDING')


class Migration(migrations.Migration):

    dependencies = [
        ('inspections', '0004_billingrecord_payment_fields'),
    ]

    operations = [
        migrations.RunPython(pending_to_unpaid, unpaid_to_pending),
    ]

