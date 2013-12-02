import os
from agent import agent
from library.system.user import User
from celery.utils.log import get_task_logger
import library.basic
logger = get_task_logger(__name__)

@agent.task
def add(x, y):
    logger.info('Adding {0} + {1}'.format(x, y))
    return x + y

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

        if AccountObject.get('sftp_only', False):
            user_obj['groups_in'].append('sftponly')
            user_obj['shell'] = '/usr/sbin/nologin'
        else:
            user_obj['groups_out'].append('sftponly')
            user_obj['shell'] = '/bin/bash'

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

        if AccountObject.get('sftp_only', False):
            os.chown(user.info()[5], 0, user.info()[3])
            os.chmod(user.info()[5], 0750)
        else:
            os.chown(user.info()[5], user.info()[2], user.info()[3])

        # Make sure domains directory exists
        library.basic.make_sure_path_exists(user.info()[5] + '/domains')
        os.chown(user.info()[5] + '/domains', user.info()[2], user.info()[3])
        os.chmod(user.info()[5] + '/domains', 0555)

    # deal with vhosts
    # deal with apps
    # deal with MySQL databases

