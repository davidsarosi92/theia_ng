# Generated for Theia NG: site-level config overrides (singleton).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('theia_ng', '0006_usersettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site_title', models.CharField(blank=True, max_length=200)),
                ('logo_url', models.CharField(blank=True, max_length=500)),
                ('schema_ttl', models.IntegerField(blank=True, null=True)),
                ('cache_version', models.CharField(blank=True, max_length=50)),
                ('cache_buster', models.PositiveIntegerField(default=0)),
                ('modified', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Site config',
                'verbose_name_plural': 'Site config',
            },
        ),
    ]
