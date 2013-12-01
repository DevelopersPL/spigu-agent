from agent import agent
from library.system.user import User
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@agent.task
def add(x, y):
    logger.info('Adding {0} + {1}'.format(x, y))
    return x + y


@agent.task
def mul(x, y):
    return x * y


@agent.task
def xsum(numbers):
    return sum(numbers)

@agent.task
def WebAccount(AccountObject):
    logger.info(repr(AccountObject))

    ##### deal with system account #####
    # Validate state
    if AccountObject['state'] not in ['active', 'locked', 'suspended', 'deleted']:
        raise Exception('Unrecognized WebAccount state value: ' + AccountObject['state'])

    if AccountObject['state'] == 'deleted':
        user = User({'username': AccountObject['username']})
        if user.exists():
            logger.info('Deleting user: ' + user.username)
            user.delete()
            # user's group is deleted automatically by deluser
    else:
        user_obj = {'username': AccountObject['username'],
                    'password': AccountObject['password'],
                    'password_login': AccountObject.get('password_login', True),
                    'groups_in': ['web'],
                    'groups_out': []}

        if AccountObject.get('false_shell', False):
            user_obj['shell'] = '/bin/false'
        else:
            user_obj['shell'] = '/bin/bash'

        if AccountObject.get('sftp_only', False):
            user_obj['groups_in'].append('sftponly')
        else:
            user_obj['groups_out'].append('sftponly')

        if AccountObject['state'] == 'active':
            user_obj['expires'] = ''
        else:
            # account is either locked or suspended, in both cases we want to disable login
            user_obj['expires'] = '1'

        user = User(user_obj)
        # state is not deleted - it means account should exist
        if not user.exists():
            logger.info('Creating user: ' + user.username)
            user.create()
        else:
            # user exists - let's make sure it is exactly what it should be
            logger.info('Modifying user: ' + user.username)
            user.modify()


    # deal with vhosts
    # deal with apps
    # deal with MySQL databases

