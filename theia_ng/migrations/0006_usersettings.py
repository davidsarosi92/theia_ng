# Generated for Theia NG: per-user settings (language, timezone, theme, nav order).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('theia_ng', '0005_logentry'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(blank=True, max_length=16)),
                ('timezone', models.CharField(blank=True, max_length=64)),
                ('theme', models.CharField(choices=[('auto', 'Auto'), ('light', 'Light'), ('dark', 'Dark')], default='auto', max_length=8)),
                ('nav_app_order', models.JSONField(blank=True, default=list)),
                ('nav_order', models.JSONField(blank=True, default=list)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='theia_ng_settings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'User settings',
                'verbose_name_plural': 'User settings',
            },
        ),
    ]
