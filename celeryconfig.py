__author__ = 'Daniel'
BROKER_URL = 'amqp://guest@marley.dondaniello.com:5672/'
# The default value is False
BROKER_USE_SSL = False

CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT=['json']

#CELERY_TIMEZONE = 'Europe/Warsaw'
CELERY_ENABLE_UTC = True

# The number of concurrent worker processes/threads/green threads executing tasks.
CELERYD_CONCURRENCY = 4

# How many messages to prefetch at a time multiplied by the number of concurrent processes. The default is 4 (four messages for each process).
CELERYD_PREFETCH_MULTIPLIER = 1

CELERY_RESULT_BACKEND = 'amqp://guest@marley.dondaniello.com:5672/'
CELERY_RESULT_SERIALIZER = 'json'
#CELERY_RESULT_PERSISTENT = True
CELERY_TASK_RESULT_EXPIRES = 86400

# The default value is False
CELERY_TRACK_STARTED = True

# The default value is False
CELERY_ACKS_LATE = True

# Send events so the worker can be monitored by tools like celerymon.
CELERY_SEND_EVENTS = True