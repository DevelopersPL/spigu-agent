FROM python:2-onbuild
CMD [ "uwsgi", "--module=spiguagent.wsgi:application", "--http=0.0.0.0:8000" ]
