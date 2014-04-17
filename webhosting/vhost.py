from __future__ import absolute_import
from celery import shared_task
import os
import shutil
from webhosting.library.system.user import User
import webhosting.library.basic as basic
from webhosting.templates import vhost_template, index_template, strtosafe

from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

vhost_dir = '/etc/nginx/sites-enabled/'

@shared_task(throws=(KeyError), bind=True)
def create(self, **UserOptions):
    user_obj = {'username': UserOptions['username'],
                'password': UserOptions['password'],
                'password_login': UserOptions.get('password_login', True),
                'groups_in': ['web'],
                'groups_out': []}

    user = User(user_obj)

    if UserOptions['state'] not in ['suspended', 'terminated']:
        for vhost in UserOptions['vhosts']:
            # Create domain directory
            basic.make_sure_path_exists(user.info()[5] + '/domains/' + vhost['name'] + '/public_html')
            os.chown(user.info()[5] + '/domains/' + vhost['name'], user.info()[2], user.info()[3])
            os.chmod(user.info()[5] + '/domains', 0555)

            # So called environment for jinja2 template
            vhost_data = {
                "username": user.username,
                "homedir": user.info()[5],
                "name": vhost['name']
            }

            with open(vhost_dir + user.username + '_' + vhost['name'] + '.conf', 'w') as vhost_file:
                vhost_file.write(vhost_template.render(vhost_data))
                vhost_file.close()

            if not os.path.exists(user.info()[5] + '/domains/' + vhost['name'] + '/public_html/index.php'):
                with open(user.info()[5] + '/domains/' + vhost['name'] + '/public_html/index.php', 'w') as vhost_file:
                    vhost_file.write(index_template.render(vhost_data))
                    vhost_file.close()

            os.chown(user.info()[5] + '/domains/' + vhost['name'] + '/public_html/index.php', user.info()[2], user.info()[3])
            os.chmod(user.info()[5] + '/domains/' + vhost['name'] + '/public_html/index.php', 0644)

            try:
                basic.run_command('/usr/sbin/nginx -t')
            except Exception:
                os.remove(vhost_dir + user.username + '_' + vhost['name'] + '.conf')
                raise

        basic.run_command('/usr/sbin/nginx -s reload')

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
    for vhost in UserOptions['vhosts']:
        os.remove(vhost_dir + user.username + '_' + vhost['name'] + '.conf')

        try:
            logger.info('Removing domain directory for ' + vhost['name'])
            shutil.rmtree(os.path.join(user.info()[5] + '/domains/', vhost['name']), True)
        except OSError:
            pass

    basic.run_command('/usr/sbin/nginx -t')
    basic.run_command('/usr/sbin/nginx -s reload')
