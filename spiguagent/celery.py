from __future__ import absolute_import

import os

from celery import Celery
from kombu import Exchange, Queue
from django.conf import settings
from celery.task.http import dispatch

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spiguagent.settings')

app = Celery('spiguagent')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
#app.conf.CELERY_QUEUES = tuple(Queue(i.keys()[0], Exchange('default'), routing_key=i.keys()[0]) for i in app.control.ping())

from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

@app.task(bind=True)
def notify(self, task_id):
    dispatch(url='http://marley.dondaniello.com:3000/api/agent/notify/' + task_id, method='POST').get()
