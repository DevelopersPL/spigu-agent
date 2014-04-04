from celery import app
from django.http import HttpResponse, Http404
from anyjson import serialize

def JsonResponse(response):
    return HttpResponse(serialize(response), content_type='application/json')

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

