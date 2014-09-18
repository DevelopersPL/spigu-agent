from __future__ import absolute_import
from celery import shared_task
import webhosting

@shared_task(bind=True, default_retry_delay=5, rate_limit=5)
def create(self, **kwargs):
    webhosting.user.create(**kwargs)
    webhosting.vhost.create(**kwargs)
    webhosting.mysql.create(**kwargs)
    webhosting.php.setup(**kwargs)
    return True

@shared_task(bind=True, default_retry_delay=5, rate_limit=5)
def lock(self, **kwargs):
    webhosting.user.create(**kwargs)
    return True

@shared_task(bind=True, default_retry_delay=5, rate_limit=5)
def suspend(self, **kwargs):
    webhosting.mysql.userdelete(**kwargs)
    webhosting.vhost.delete(remove_dirs=False, **kwargs)
    webhosting.user.create(**kwargs)
    return True

@shared_task(bind=True, default_retry_delay=5, rate_limit=5)
def terminate(self, **kwargs):
    webhosting.mysql.delete(**kwargs)
    webhosting.vhost.delete(**kwargs)
    webhosting.user.unsnapshot(**kwargs)
    webhosting.user.delete(**kwargs)
    return True

@shared_task(bind=True, default_retry_delay=5, rate_limit=5)
def transfer(self, **kwargs):
    webhosting.user.transfer(**kwargs)
    webhosting.mysql.transfer(**kwargs)
    return True
