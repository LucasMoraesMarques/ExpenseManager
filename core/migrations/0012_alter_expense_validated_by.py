# Generated by Django 4.1 on 2023-03-17 20:30

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("core", "0011_alter_expensegroup_hash_id")]

    operations = [
        migrations.AlterField(
            model_name="expense",
            name="validated_by",
            field=models.ManyToManyField(
                blank=True,
                null=True,
                related_name="validated_expenses",
                to=settings.AUTH_USER_MODEL,
            ),
        )
    ]
