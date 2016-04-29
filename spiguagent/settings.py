from __future__ import absolute_import
import os
# ^^^ The above is required if you want to import from the celery
# library.  If you don't have this then `from celery.schedules import`
# becomes `proj.celery.schedules` in Python 2.x since it allows
# for relative imports by default.

# Celery settings
BROKER_URL = os.environ['SPIGU_AGENT_AMQP_CONNECTION']
# The default value is False
BROKER_USE_SSL = True

CELERY_TASK_SERIALIZER = 'json'
#: Only add pickle to this list if your broker is secured
#: from unwanted access (see userguide/security.html)
CELERY_ACCEPT_CONTENT=['json']

#CELERY_TIMEZONE = 'Europe/Warsaw'
CELERY_ENABLE_UTC = True

# The number of concurrent worker processes/threads/green threads executing tasks.
CELERYD_CONCURRENCY = 4

# How many messages to prefetch at a time multiplied by the number of concurrent processes. The default is 4 (four messages for each process).
CELERYD_PREFETCH_MULTIPLIER = 1

CELERY_RESULT_BACKEND = os.environ['SPIGU_AGENT_AMQP_CONNECTION']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_RESULT_PERSISTENT = True
#CELERY_TASK_RESULT_EXPIRES = 86400

# The default value is False
CELERY_TRACK_STARTED = True

# The default value is False
CELERY_ACKS_LATE = True

# Send events so the worker can be monitored by tools like celerymon.
CELERY_SEND_EVENTS = True

CELERY_DISABLE_RATE_LIMITS = False
BROKER_HEARTBEAT = 10

"""
Django settings for spiguagent project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'rdk=72lxy@tzml353bsno($96t(!+(79%%s&te$kd3-jy6xf85'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = (
#    'django.contrib.admin',
#    'django.contrib.auth',
#    'django.contrib.contenttypes',
#    'django.contrib.sessions',
#    'django.contrib.messages',
#    'django.contrib.staticfiles',
     'webhosting',
     'rest_framework'
)

MIDDLEWARE_CLASSES = (
#    'django.contrib.sessions.middleware.SessionMiddleware',
#    'django.middleware.common.CommonMiddleware',
#    'django.middleware.csrf.CsrfViewMiddleware',
#    'django.contrib.auth.middleware.AuthenticationMiddleware',
#    'django.contrib.messages.middleware.MessageMiddleware',
#    'django.middleware.clickjacking.XFrameOptionsMiddleware',
#    'spiguagent.logging.ExceptionLoggingMiddleware'
)

ROOT_URLCONF = 'spiguagent.urls'

WSGI_APPLICATION = 'spiguagent.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'pl'

TIME_ZONE = 'Europe/Warsaw'

USE_I18N = False

USE_L10N = False

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'

REST_FRAMEWORK = {

}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        # Include the default Django email handler for errors
        # This is what you'd get without configuring logging at all.
        'mail_admins': {
            'class': 'django.utils.log.AdminEmailHandler',
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            # But the emails are plain text by default - HTML is nicer
            'include_html': True,
        },
        # Log to a text file that can be rotated by logrotate
        'logfile': {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': 'spigu-agent.log'
        },
    },
    'loggers': {
        # Again, default Django configuration to email unhandled exceptions
        'django.request': {
            'handlers': ['logfile'],
            'level': 'ERROR',
            'propagate': True,
        },
        # Might as well log any errors anywhere else in Django
        'django': {
            'handlers': ['logfile'],
            'level': 'ERROR',
            'propagate': False,
        },
        # Your own app - this assumes all your logger names start with "myapp."
        'myapp': {
            'handlers': ['logfile'],
            'level': 'DEBUG',  # Or maybe INFO or WARNING
            'propagate': False
        },
    }
}

try:
    from local_settings import *  # noqa
except ImportError:
    pass
