from __future__ import absolute_import
from celery import shared_task
import webhosting

@shared_task(bind=True)
def create(self, **kwargs):
    webhosting.user.create(**kwargs)
    webhosting.vhost.create(**kwargs)
    webhosting.mysql.create(**kwargs)
    webhosting.php.setup(**kwargs)
    return True

@shared_task(bind=True)
def delete(self, **kwargs):
    webhosting.mysql.delete(**kwargs)
    webhosting.vhost.delete(**kwargs)
    webhosting.user.unsnapshot(**kwargs)
    webhosting.user.delete(**kwargs)
    return True
