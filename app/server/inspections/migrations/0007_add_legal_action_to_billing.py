# Generated manually for legal action field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inspections', '0006_alter_billingrecord_payment_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='billingrecord',
            name='legal_action',
            field=models.CharField(
                choices=[
                    ('NONE', 'None'),
                    ('SHOW_CAUSE_ORDER', 'Show Cause Order'),
                    ('LEGAL_EVALUATION', 'For Legal Evaluation'),
                    ('FOR_ENDORSEMENT', 'For Endorsement'),
                    ('LEGAL_ESCALATION', 'Legal Escalation'),
                ],
                default='NONE',
                help_text='Current legal action status',
                max_length=30
            ),
        ),
    ]

