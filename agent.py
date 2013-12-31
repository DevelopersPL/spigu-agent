#!/usr/bin/python
from celery import Celery

agent = Celery('spigu',
             include=['tasks'])

agent.config_from_object('celeryconfig')

if __name__ == '__main__':
#    agent.start()
    agent.worker_main()

# http://docs.celeryproject.org/en/latest/userguide/workers.html#persistent-revokes
# --statedb=/var/run/celery/worker.state

# /usr/local/spigu/agent.py --loglevel=info --autoreload --statedb=/tmp/spigu-agent.state