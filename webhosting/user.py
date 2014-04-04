from __future__ import absolute_import
from celery import shared_task
import os
from webhosting.library.system.user import User
import webhosting.library.basic as basic

@shared_task(throws=(KeyError), bind=True)
def create(self, **UserOptions):
    user_obj = {'username': UserOptions['username'],
                'password': UserOptions['password'],
                'password_login': UserOptions.get('password_login', True),
                'groups_in': ['web'],
                'groups_out': []}

    if UserOptions.get('sftp_only', False):
        user_obj['groups_in'].append('sftponly')
        user_obj['shell'] = '/usr/sbin/nologin'
    else:
        user_obj['groups_out'].append('sftponly')
        user_obj['shell'] = '/bin/bash'

    if UserOptions['state'] == 'active':
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

    if UserOptions.get('sftp_only', False):
        os.chown(user.info()[5], 0, user.info()[3])
        os.chmod(user.info()[5], 0750)
    else:
        os.chown(user.info()[5], user.info()[2], user.info()[3])

    # XATTRs - allow www-data to access userdir
    # setfacl -m u:www-data:rX /home/web34/
    basic.run_command('/bin/setfacl -m u:www-data:rX /home/' + user.username)

    # Make sure domains directory exists
    basic.make_sure_path_exists(user.info()[5] + '/domains')
    os.chown(user.info()[5] + '/domains', user.info()[2], user.info()[3])
    os.chmod(user.info()[5] + '/domains', 0555)

@shared_task(throws=(KeyError), bind=True)
def delete(self, **UserOptions):
    user = User({'username': UserOptions['username']})
    if user.exists():
        logger.info('Deleting user: ' + user.username)
        user.delete()
        # user's group is deleted automatically by deluser
