import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kole_backend.settings')

app = Celery('kole_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
