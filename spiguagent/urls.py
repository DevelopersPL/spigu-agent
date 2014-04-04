from django.conf.urls import patterns, include, url
import celery_views, views

urlpatterns = patterns('',
    url(r'^api/tasks/(?P<task_name>.+?)/', celery_views.apply),
    url(r'^api/tasks/(?P<task_id>[\w\d\-]+)/done/?$', celery_views.is_task_successful,
        name='celery-is_task_successful'),
    url(r'^api/tasks/(?P<task_id>[\w\d\-]+)/status/?$', celery_views.task_status,
        name='celery-task_status'),
    url(r'^api/tasks/?$', celery_views.registered_tasks),
    url(r'^api/nodes/?$', views.ping),
    url(r'^api/inspect/?$', views.inspect),
)