# Generated by Django 4.1 on 2023-03-25 20:36

from django.db import migrations, models
import phonenumber_field.modelfields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_alter_expense_date_alter_paymentmethod_limit_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='address_number',
            field=models.IntegerField(blank=True, null=True, verbose_name='Number'),
        ),
        migrations.AddField(
            model_name='user',
            name='city',
            field=models.CharField(blank=True, max_length=128, null=True, verbose_name='City'),
        ),
        migrations.AddField(
            model_name='user',
            name='district',
            field=models.CharField(blank=True, max_length=128, null=True, verbose_name='District'),
        ),
        migrations.AddField(
            model_name='user',
            name='fcm_token',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Firebase Token'),
        ),
        migrations.AddField(
            model_name='user',
            name='google_id',
            field=models.CharField(blank=True, max_length=128, null=True, verbose_name='Google Account Id'),
        ),
        migrations.AddField(
            model_name='user',
            name='phone',
            field=phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, null=True, region=None, verbose_name='Phone Number'),
        ),
        migrations.AddField(
            model_name='user',
            name='state',
            field=models.CharField(blank=True, choices=[('AC', 'AC'), ('AL', 'AL'), ('AP', 'AP'), ('AM', 'AM'), ('BA', 'BA'), ('CE', 'CE'), ('DF', 'DF'), ('ES', 'ES'), ('GO', 'GO'), ('MA', 'MA'), ('MT', 'MT'), ('MS', 'MS'), ('MG', 'MG'), ('PA', 'PA'), ('PB', 'PB'), ('PR', 'PR'), ('PE', 'PE'), ('PI', 'PI'), ('RJ', 'RJ'), ('RN', 'RN'), ('RS', 'RS'), ('RO', 'RO'), ('RR', 'RR'), ('SC', 'SC'), ('SP', 'SP'), ('SE', 'SE'), ('TO', 'TO')], max_length=2, null=True, verbose_name='State'),
        ),
        migrations.AddField(
            model_name='user',
            name='street',
            field=models.CharField(blank=True, max_length=128, null=True, verbose_name='Street'),
        ),
        migrations.AddField(
            model_name='user',
            name='zip_code',
            field=models.CharField(blank=True, max_length=8, verbose_name='Zip Code'),
        ),
    ]