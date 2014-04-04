#!/usr/bin/python
from __future__ import absolute_import
import socket
from spiguagent.celery import app

app.conf.CELERY_DEFAULT_QUEUE = socket.gethostname()
app.conf.CELERY_DEFAULT_ROUTING_KEY = socket.gethostname()

if __name__ == '__main__':
    app.worker_main()
