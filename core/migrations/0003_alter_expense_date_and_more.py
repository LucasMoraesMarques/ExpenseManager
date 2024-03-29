# Generated by Django 4.1 on 2022-08-05 02:14

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("core", "0002_expense_expensegroup_wallet_tag_regarding_and_more")]

    operations = [
        migrations.AlterField(
            model_name="expense",
            name="date",
            field=models.DateField(
                default=datetime.datetime(2022, 8, 5, 2, 14, 2, 625618),
                verbose_name="Expense Date",
            ),
        ),
        migrations.AlterField(
            model_name="paymentmethod",
            name="compensation_date",
            field=models.DateField(
                default=datetime.datetime(2022, 8, 5, 2, 14, 2, 624377),
                verbose_name="Payment Due Date",
            ),
        ),
        migrations.AlterField(
            model_name="regarding",
            name="balance_json",
            field=models.JSONField(
                default=dict, null=True, verbose_name="Balance Data"
            ),
        ),
        migrations.AlterField(
            model_name="regarding",
            name="start_date",
            field=models.DateField(
                default=datetime.datetime(2022, 8, 5, 2, 14, 2, 623224),
                verbose_name="Start Date",
            ),
        ),
    ]
