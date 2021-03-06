# Taken from https://raw.githubusercontent.com/celery/django-celery/3.1/djcelery/views.py
# Modified!
from __future__ import absolute_import, unicode_literals

from functools import wraps

from django.http import HttpResponse, Http404

from anyjson import serialize

from celery import states
from celery.registry import tasks
from celery.result import AsyncResult
from celery.utils import get_full_cls_name, kwdict
from celery.utils.encoding import safe_repr

# Ensure built-in tasks are loaded for task_list view
import celery.task  # noqa


def JsonResponse(response):
    return HttpResponse(serialize(response), content_type='application/json')


def task_view(task):
    """Decorator turning any task into a view that applies the task
    asynchronously. Keyword arguments (via URLconf, etc.) will
    supercede GET or POST parameters when there are conflicts.

    Returns a JSON dictionary containing the keys ``ok``, and
        ``task_id``.

    """

    def _applier(request, **options):
        kwargs = kwdict(request.method == 'POST' and
                        request.POST or request.GET)
        # no multivalue
        kwargs = dict(((k, v) for k, v in kwargs.iteritems()), **options)
        queue = kwargs['server']
        del kwargs['server']
        result = task.apply_async(kwargs=kwargs, queue=queue)
        return JsonResponse({'ok': 'true', 'task_id': result.task_id})

    return _applier


def apply(request, task_name):
    """View applying a task.

    **Note:** Please use this with caution. Preferably you shouldn't make this
        publicly accessible without ensuring your code is safe!

    """
    try:
        task = tasks[task_name]
    except KeyError:
        raise Http404('apply: no such task')
    return task_view(task)(request)


def is_task_successful(request, task_id):
    """Returns task execute status in JSON format."""
    return JsonResponse({'task': {
        'id': task_id,
        'executed': AsyncResult(task_id).successful(),
    }})


def task_status(request, task_id):
    """Returns task status and result in JSON format."""
    result = AsyncResult(task_id)
    #print dir(result)
    print result.state
    state, retval, success = result.state, False, result.successful()
    response_data = dict(task_id=task_id, status=state, result=retval, success=success)
    if state in states.EXCEPTION_STATES:
        traceback = result.traceback
        response_data.update({'result': safe_repr(retval),
                              'exc': get_full_cls_name(retval.__class__),
                              'traceback': traceback})
    return JsonResponse(response_data)

def registered_tasks(request):
    """View returning all defined tasks as a JSON object."""
    return JsonResponse({'regular': tasks.regular().keys(),
                         'periodic': tasks.periodic().keys()})


def task_webhook(fun):
    """Decorator turning a function into a task webhook.

    If an exception is raised within the function, the decorated
    function catches this and returns an error JSON response, otherwise
    it returns the result as a JSON response.


    Example:

    .. code-block:: python

        @task_webhook
        def add(request):
            x = int(request.GET['x'])
            y = int(request.GET['y'])
            return x + y

        def view(request):
            response = add(request)
            print(response.content)

    Gives::

        "{'status': 'success', 'retval': 100}"

    """

    @wraps(fun)
    def _inner(*args, **kwargs):
        try:
            retval = fun(*args, **kwargs)
        except Exception as exc:
            response = {'status': 'failure', 'reason': safe_repr(exc)}
        else:
            response = {'status': 'success', 'retval': retval}

        return JsonResponse(response)

    return _inner