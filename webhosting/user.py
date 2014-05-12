from __future__ import absolute_import
from celery import shared_task
import os
import shutil
from webhosting.library.system.user import User
import webhosting.library.basic as basic
import webhosting.library.system.btrfs as btrfs

from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

FILES_DIR = os.path.dirname(os.path.realpath(__file__)) + '/library/files/'

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

    if UserOptions['state'] in ['suspended', 'locked']:
        # account is either locked or suspended, in both cases we want to disable login
        user_obj['expires'] = '1'
    else:
        user_obj['expires'] = ''

    user = User(user_obj)
    # state is not deleted - it means account should exist
    if not user.exists():
        logger.info('Creating user: ' + user.username)
        if not os.path.exists('/home/' + user.username):
            basic.run_command('/sbin/btrfs subvolume create /home/' + user.username)
        user.create()
        basic.copytree('/etc/skel', user.pwd_info().pw_dir, symlinks=True) # since the homedir existed before user.create(), adduser does not copy skel
        basic.run_command('/sbin/btrfs qgroup create 1/' + str(user.pwd_info().pw_uid) + ' ' + user.pwd_info().pw_dir)
        basic.run_command('/sbin/btrfs qgroup assign 0/' + str(btrfs.get_subvolume_id(user.pwd_info().pw_dir)) + ' 1/' + str(user.pwd_info().pw_uid) + ' ' + user.pwd_info().pw_dir)
    else:
        # user exists - let's make sure it is exactly what it should be
        logger.info('Modifying user: ' + user.username)
        user.modify()

    # set quota
    quota = UserOptions['limits'].get('quota', 0)
    basic.run_command('/sbin/btrfs qgroup limit ' + str(quota) + ' 1/' + str(user.pwd_info().pw_uid) + ' ' + user.pwd_info().pw_dir)

    # XATTRs - allow www-data to access userdir
    # setfacl -m u:www-data:rX /home/web34/
    basic.run_command('/bin/setfacl -m u:www-data:rX ' + user.pwd_info().pw_dir)
    os.chmod(user.pwd_info().pw_dir, 0750)

    # Make sure domains directory exists
    basic.ensure_path(user.pwd_info().pw_dir + '/domains')
    os.chown(user.pwd_info().pw_dir + '/domains', user.pwd_info().pw_uid, user.pwd_info().pw_gid)
    os.chmod(user.pwd_info().pw_dir + '/domains', 0555)

    shutil.copyfile(FILES_DIR + '.webuser', user.pwd_info().pw_dir + '/.webuser')

    basic.rec_chown(user.pwd_info().pw_dir, user.pwd_info().pw_uid, user.pwd_info().pw_gid)

    basic.run_command('/sbin/start session-init-setup')

@shared_task(throws=(KeyError), bind=True)
def delete(self, **UserOptions):
    user = User({'username': UserOptions['username']})
    if user.exists():
        logger.info('Deleting user: ' + user.username)
        if os.path.exists(user.pwd_info().pw_dir):
            basic.run_command('/sbin/btrfs subvolume delete ' + user.pwd_info().pw_dir)
        user.delete()
        # user's group is deleted automatically by deluser
        basic.run_command('/sbin/btrfs qgroup destroy 1/' + str(user.pwd_info().pw_uid) + ' ' + user.pwd_info().pw_dir, check_rc=False)

@shared_task(throws=(KeyError), bind=True)
def snapshot(self, **UserOptions):
    user = User({'username': UserOptions['username']})
    if user.exists():
        logger.info('Snapshotting user: ' + user.username)
        if not os.path.exists('/mnt/snapshots/' + user.username):
            basic.run_command('/sbin/btrfs subvolume snapshot -r ' + user.pwd_info().pw_dir + ' /mnt/snapshots/' + user.username)
            basic.run_command('/sbin/btrfs qgroup assign 0/' + btrfs.get_subvolume_id('/mnt/snapshots/' + user.username) + ' 1/' + user.pwd_info().pw_uid + ' /mnt/snapshots/' + user.username)

            if os.path.exists(user.pwd_info().pw_dir + '/snapshot'):
                os.unlink(user.pwd_info().pw_dir + '/snapshot')

            os.symlink('/mnt/snapshots/' + user.username, user.pwd_info().pw_dir + '/snapshot')
        else:
            raise Exception('Snapshot directory already exists!')
    else:
        raise Exception('User does not exist.')

@shared_task(throws=(KeyError), bind=True)
def unsnapshot(self, **UserOptions):
    user = User({'username': UserOptions['username']})
    if user.exists():
        logger.info('Snapshotting user: ' + user.username)
        if os.path.exists('/mnt/snapshots/' + user.username):
            basic.run_command('/sbin/btrfs subvolume delete /mnt/snapshots/' + user.username)
        if os.path.exists(user.pwd_info().pw_dir + '/snapshot'):
            os.unlink(user.pwd_info().pw_dir + '/snapshot')
    else:
        raise Exception('User does not exist.')
