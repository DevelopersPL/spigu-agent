from django.conf.urls import patterns, include, url
import celery_views, views
from rest_framework import viewsets, routers

urlpatterns = patterns('',
    # Wrappers around actions
    url(r'^api/webserver/create/?$', views.webhosting_create),
    url(r'^api/webserver/lock/?$', views.webhosting_lock),
    url(r'^api/webserver/suspend/?$', views.webhosting_suspend),
    url(r'^api/webserver/delete/?$', views.webhosting_delete),
    url(r'^api/webserver/snapshot/?$', views.webhosting_snapshot),
    url(r'^api/webserver/unsnapshot/?$', views.webhosting_unsnapshot),
    url(r'^api/webserver/vhost/create/?$', views.webhosting_vhost_create),
    url(r'^api/webserver/vhost/delete/?$', views.webhosting_vhost_delete),
    url(r'^api/webserver/mysql/create/?$', views.webhosting_mysql_create),
    url(r'^api/webserver/mysql/delete/?$', views.webhosting_mysql_delete),
    url(r'^api/webserver/php/setup/?$', views.webhosting_php_setup),

    # Direct access to tasks
    url(r'^api/apply/(?P<task_name>.+?)/?$', celery_views.apply),
    url(r'^api/tasks/(?P<task_id>[\w\d\-]+)/done/?$', celery_views.is_task_successful,
        name='celery-is_task_successful'),
    url(r'^api/tasks/(?P<task_id>[\w\d\-]+)/status/?$', celery_views.task_status,
        name='celery-task_status'),
    url(r'^api/tasks/?$', celery_views.registered_tasks),
    url(r'^api/ping/?$', views.ping),
    url(r'^api/inspect/?$', views.inspect),
)
