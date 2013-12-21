# -*- coding: utf-8 -*-
import os
import time
from agent import agent
from library.system.user import User
from celery.utils.log import get_task_logger
import library.basic
logger = get_task_logger(__name__)
from templates import vhost_template
import config
from lxml import etree

@agent.task
def add(x, y):
    logger.info('Adding {0} + {1}'.format(x, y))
    logger.info('Waiting 10 seconds')
    time.sleep(10)
    return x + y

@agent.task(throws=(KeyError), bind=True)
def WebAccount(self, **AccountObject):
    logger.info(repr(AccountObject))

    ############################### deal with system account ###############################
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

    ############################### deal with vhosts ###############################
    for vhost in AccountObject['vhosts']:
        # Create domain directory
        library.basic.make_sure_path_exists(user.info()[5] + '/domains/' + vhost['name'])
        os.chown(user.info()[5] + '/domains/' + vhost['name'], user.info()[2], user.info()[3])
        os.chmod(user.info()[5] + '/domains', 0555)

        # So called environment for jinja2 template
        vhost_data = {
            "username": user.username,
            "homedir": user.info()[5],
            "name": vhost['name'],
            "index_files": "index.php, index.html",
            "appmap": vhost['appmap']
        }
        with open(config.LSWS_VHOST_DIR + user.username + '_' + vhost['name'] + '.xml', 'w') as vhost_file:
            vhost_file.write(vhost_template.render(vhost_data))
            vhost_file.close()

        # add the vhost to main config
        httpd_config = etree.parse(config.LSWS_CONFIG_PATH)
        # print etree.tostring(httpd_config, pretty_print=True)

        # look for the vhost in config

        # save global config
        httpd_config.write(config.LSWS_CONFIG_PATH, xml_declaration=True, pretty_print=True, encoding="UTF-8")



    # deal with apps
    # deal with MySQL databases

