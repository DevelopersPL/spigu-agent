from __future__ import absolute_import
from spiguagent.celery import app
from celery.utils import kwdict
from celery import chain, group, chord
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.renderers import JSONRenderer
import webhosting


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)

def ping(request):
    return JSONResponse(app.control.ping(timeout=1))

def inspect(request):
    i = app.control.inspect()
    return JSONResponse({'active': i.active(),
                         'registered': i.registered(),
                         'scheduled': i.scheduled(),
                         'stats': i.stats(),
                         'report': i.report(),
    })

@api_view(['POST'])
def webhosting_create(request, **options):
    result = webhosting.sets.create.apply_async(kwargs=request.DATA, queue=request.DATA['server'])
    return JSONResponse({'ok': 'true', 'task_id': result.task_id})

@api_view(['POST'])
def webhosting_lock(request, **options):
    result = webhosting.sets.lock.apply_async(kwargs=request.DATA, queue=request.DATA['server'])
    return JSONResponse({'ok': 'true', 'task_id': result.task_id})

@api_view(['POST'])
def webhosting_suspend(request, **options):
    result = webhosting.sets.suspend.apply_async(kwargs=request.DATA, queue=request.DATA['server'])
    return JSONResponse({'ok': 'true', 'task_id': result.task_id})

@api_view(['POST'])
def webhosting_terminate(request, **options):
    result = webhosting.sets.terminate.apply_async(kwargs=request.DATA, queue=request.DATA['server'])
    return JSONResponse({'ok': 'true', 'task_id': result.task_id})

@api_view(['POST'])
def webhosting_vhost_create(request, **options):
    result = webhosting.vhost.create.apply_async(kwargs=request.DATA, queue=request.DATA['server'])
    return JSONResponse({'ok': 'true', 'task_id': result.task_id})

@api_view(['POST'])
def webhosting_vhost_delete(request, **options):
    result = webhosting.vhost.delete.apply_async(kwargs=request.DATA, queue=request.DATA['server'])
    return JSONResponse({'ok': 'true', 'task_id': result.task_id})

@api_view(['POST'])
def webhosting_mysql_create(request, **options):
    result = webhosting.mysql.create.apply_async(kwargs=request.DATA, queue=request.DATA['server'])
    return JSONResponse({'ok': 'true', 'task_id': result.task_id})

@api_view(['POST'])
def webhosting_mysql_delete(request, **options):
    result = webhosting.mysql.delete.apply_async(kwargs=request.DATA, queue=request.DATA['server'])
    return JSONResponse({'ok': 'true', 'task_id': result.task_id})

@api_view(['POST'])
def webhosting_php_setup(request, **options):
    result = webhosting.php.setup.apply_async(kwargs=request.DATA, queue=request.DATA['server'])
    return JSONResponse({'ok': 'true', 'task_id': result.task_id})

@api_view(['POST'])
def webhosting_snapshot(request, **options):
    result = webhosting.user.snapshot.apply_async(kwargs=request.DATA, queue=request.DATA['server'])
    return JSONResponse({'ok': 'true', 'task_id': result.task_id})

@api_view(['POST'])
def webhosting_unsnapshot(request, **options):
    result = webhosting.user.unsnapshot.apply_async(kwargs=request.DATA, queue=request.DATA['server'])
    return JSONResponse({'ok': 'true', 'task_id': result.task_id})
