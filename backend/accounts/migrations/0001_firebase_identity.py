"""The Firebase uid to Django user link (see accounts/models.py)."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FirebaseIdentity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uid', models.CharField(max_length=128, unique=True)),
                ('provider', models.CharField(blank=True, max_length=64)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('email_verified', models.BooleanField(default=False)),
                ('display_name', models.CharField(blank=True, max_length=150)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_login_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='firebase_identity', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Firebase identity',
                'verbose_name_plural': 'Firebase identities',
                'ordering': ['-created_at', 'pk'],
            },
        ),
    ]
