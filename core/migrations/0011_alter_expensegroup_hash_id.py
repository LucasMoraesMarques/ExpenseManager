# Generated by Django 4.1 on 2023-03-17 12:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("core", "0010_expensegroup_hash_id_alter_expense_date_and_more")]

    operations = [
        migrations.AlterField(
            model_name="expensegroup",
            name="hash_id",
            field=models.CharField(
                blank=True, max_length=16, null=True, verbose_name="Hash ID"
            ),
        )
    ]
