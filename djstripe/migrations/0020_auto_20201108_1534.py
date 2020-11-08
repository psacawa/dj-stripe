# Generated by Django 3.1.2 on 2020-11-08 15:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("djstripe", "0019_auto_20201031_1753"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bankaccount",
            name="account_holder_name",
            field=models.TextField(
                blank=True,
                help_text="The name of the person or business that owns the bank account.",
                max_length=5000,
            ),
        ),
    ]