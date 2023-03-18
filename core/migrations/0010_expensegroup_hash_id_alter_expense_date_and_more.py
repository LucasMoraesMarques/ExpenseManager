# Generated by Django 4.1 on 2023-03-17 11:57

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("core", "0009_alter_item_expense")]

    operations = [
        migrations.AddField(
            model_name="expensegroup",
            name="hash_id",
            field=models.CharField(default="", max_length=16, verbose_name="Hash ID"),
        ),
        migrations.AlterField(
            model_name="expense",
            name="date",
            field=models.DateField(
                default=datetime.date(2023, 3, 17), verbose_name="Expense Date"
            ),
        ),
        migrations.AlterField(
            model_name="regarding",
            name="start_date",
            field=models.DateField(
                default=datetime.date(2023, 3, 17), verbose_name="Start Date"
            ),
        ),
    ]