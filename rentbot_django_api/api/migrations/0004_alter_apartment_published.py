# Generated by Django 4.2.13 on 2024-05-31 16:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_rename_chat_id_task_user_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='apartment',
            name='published',
            field=models.DateTimeField(),
        ),
    ]
