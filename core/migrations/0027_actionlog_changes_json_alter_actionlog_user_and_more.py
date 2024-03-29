# Generated by Django 4.1 on 2023-04-05 00:36

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_alter_expense_date_alter_regarding_start_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='actionlog',
            name='changes_json',
            field=models.JSONField(blank=True, default=dict, null=True, verbose_name='Changes JSON'),
        ),
        migrations.AlterField(
            model_name='actionlog',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='performed_actions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='expense',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='created_expenses', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='expense',
            name='date',
            field=models.DateField(default=datetime.date(2023, 4, 5), verbose_name='Expense Date'),
        ),
        migrations.AlterField(
            model_name='expense',
            name='regarding',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='expenses', to='core.regarding'),
        ),
        migrations.AlterField(
            model_name='membership',
            name='group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='core.expensegroup'),
        ),
        migrations.AlterField(
            model_name='membership',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='my_memberships', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='notification',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='payment',
            name='payer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='paid_expenses', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='payment',
            name='payment_method',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='core.paymentmethod'),
        ),
        migrations.AlterField(
            model_name='paymentmethod',
            name='wallet',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_methods', to='core.wallet'),
        ),
        migrations.AlterField(
            model_name='regarding',
            name='expense_group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regardings', to='core.expensegroup'),
        ),
        migrations.AlterField(
            model_name='regarding',
            name='start_date',
            field=models.DateField(default=datetime.date(2023, 4, 5), verbose_name='Start Date'),
        ),
        migrations.AlterField(
            model_name='tag',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_tags', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='wallet',
            name='owner',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='wallet', to=settings.AUTH_USER_MODEL),
        ),
    ]
