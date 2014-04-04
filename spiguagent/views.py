from celery import app
from celery_views import JsonResponse
from celery.utils import kwdict

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

def webhosting_create(request, **options):
    kwargs = kwdict(request.method == 'POST' and request.POST or request.GET)
    kwargs = dict(((k, v) for k, v in kwargs.iteritems()), **options)  # no multivalue
    queue = kwargs['server']
    del kwargs['server']
    result = webhosting.user.create.apply_async(kwargs=kwargs, queue=queue)
    return JsonResponse({'ok': 'true', 'task_id': result.task_id})