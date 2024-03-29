# Generated by Django 4.1 on 2023-10-21 21:20

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0033_expense_payment_status_alter_expense_date_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="expense",
            name="date",
            field=models.DateField(
                default=datetime.date(2023, 10, 21), verbose_name="Expense Date"
            ),
        ),
        migrations.AlterField(
            model_name="regarding",
            name="start_date",
            field=models.DateField(
                default=datetime.date(2023, 10, 21), verbose_name="Start Date"
            ),
        ),
    ]
