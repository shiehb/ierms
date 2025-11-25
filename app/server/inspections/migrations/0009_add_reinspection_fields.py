# Generated migration for reinspection tracking

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inspections', '0008_alter_compliancequota_law'),
    ]

    operations = [
        migrations.AddField(
            model_name='inspection',
            name='is_reinspection',
            field=models.BooleanField(default=False, help_text='Flag to identify if this is a reinspection'),
        ),
        migrations.AddField(
            model_name='inspection',
            name='previous_inspection',
            field=models.ForeignKey(
                blank=True,
                help_text='Link to the previous inspection this reinspection is based on',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reinspections',
                to='inspections.inspection'
            ),
        ),
    ]



