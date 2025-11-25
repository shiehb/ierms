from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('inspections', '0003_noticeoforder_contact_person_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='billingrecord',
            name='payment_confirmed_at',
            field=models.DateTimeField(blank=True, help_text='Timestamp when payment was confirmed', null=True),
        ),
        migrations.AddField(
            model_name='billingrecord',
            name='payment_confirmed_by',
            field=models.ForeignKey(blank=True, help_text='User who confirmed the payment', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='billings_confirmed_paid', to='users.user'),
        ),
        migrations.AddField(
            model_name='billingrecord',
            name='payment_date',
            field=models.DateField(blank=True, help_text='Date when payment was confirmed', null=True),
        ),
        migrations.AddField(
            model_name='billingrecord',
            name='payment_notes',
            field=models.TextField(blank=True, help_text='Internal notes when tagging this billing as paid'),
        ),
        migrations.AddField(
            model_name='billingrecord',
            name='payment_reference',
            field=models.CharField(blank=True, help_text='Official receipt or reference number for the payment', max_length=100),
        ),
        migrations.AddField(
            model_name='billingrecord',
            name='payment_status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('PAID', 'Paid')], default='PENDING', help_text='Current payment status', max_length=20),
        ),
    ]

