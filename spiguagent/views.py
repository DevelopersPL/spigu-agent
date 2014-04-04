from celery import app
from celery_views import JsonResponse

def ping(request):
    return JsonResponse(app.control.ping(timeout=1))

def inspect(request):
    i = app.control.inspect()
    return JsonResponse({'active': i.active(),
                         'registered': i.registered(),
                         'scheduled': i.scheduled(),
                         'stats': i.stats(),
                         'report': i.report(),
    })

def webhosting_create(request):
    kwargs = kwdict(request.method == 'POST' and
                    request.POST or request.GET)
    # no multivalue
    kwargs = dict(((k, v) for k, v in kwargs.iteritems()), **options)
    result = task.apply_async(kwargs=kwargs)
    return JsonResponse({'ok': 'true', 'task_id': result.task_id})