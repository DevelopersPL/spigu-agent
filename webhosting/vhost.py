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
            basic.ensure_path(user.info()[5] + '/domains/' + vhost['name'] + '/public_html')
            os.chown(user.info()[5] + '/domains/' + vhost['name'], user.info()[2], user.info()[3])
            os.chmod(user.info()[5] + '/domains', 0555)

            # So called environment for jinja2 template
            vhost_data = {
                'username': user.username,
                'homedir': user.info()[5],
                'name': vhost['name'],
                'domains': vhost['domains'],
                'rewrite_catchall': vhost.get('rewrite_catchall', '=404'),
                'ssl': UserOptions.get('ssl', False)
            }

            with open(vhost_dir + user.username + '_' + vhost['name'] + '.conf', 'w') as f:
                f.write(vhost_template.render(vhost_data))

            if not os.path.exists(user.info()[5] + '/domains/' + vhost['name'] + '/public_html/index.php'):
                with open(user.info()[5] + '/domains/' + vhost['name'] + '/public_html/index.php', 'w') as f:
                    f.write(index_template.render(vhost_data))

            os.chown(user.info()[5] + '/domains/' + vhost['name'] + '/public_html/index.php', user.info()[2], user.info()[3])
            os.chmod(user.info()[5] + '/domains/' + vhost['name'] + '/public_html/index.php', 0644)

            """
            if vhost.get('ssl', False):
                with open('/etc/nginx/ssl/' + vhost['name'] + '.pem', 'w') as f:
                    f.write(vhost.get('ssl_pem'))
                os.chmod('/etc/nginx/ssl/' + vhost['name'] + '.pem', 0600)

                with open('/etc/nginx/ssl/' + vhost['name'] + '.key', 'w') as f:
                    f.write(vhost.get('ssl_key'))
                os.chmod('/etc/nginx/ssl/' + vhost['name'] + '.key', 0600)
            """

            if UserOptions.get('ssl', False):
                with open('/etc/nginx/ssl/' + vhost['name'] + '.pem', 'w') as f:
                    f.write(UserOptions.get('ssl_pem'))
                os.chmod('/etc/nginx/ssl/' + vhost['name'] + '.pem', 0600)

                with open('/etc/nginx/ssl/' + vhost['name'] + '.key', 'w') as f:
                    f.write(UserOptions.get('ssl_key'))
                os.chmod('/etc/nginx/ssl/' + vhost['name'] + '.key', 0600)


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
    basic.ensure_path(user.info()[5] + '/domains')
    os.chown(user.info()[5] + '/domains', user.info()[2], user.info()[3])
    os.chmod(user.info()[5] + '/domains', 0555)

@shared_task(throws=(KeyError), bind=True)
def delete(self, remove_dirs=True, **UserOptions):
    user = User({'username': UserOptions['username']})
    for vhost in UserOptions['vhosts']:
        os.remove(vhost_dir + user.username + '_' + vhost['name'] + '.conf')

        if os.path.exists('/etc/nginx/ssl/' + vhost['name'] + '.pem'):
             os.unlink('/etc/nginx/ssl/' + vhost['name'] + '.pem')

        if os.path.exists('/etc/nginx/ssl/' + vhost['name'] + '.key'):
             os.unlink('/etc/nginx/ssl/' + vhost['name'] + '.key')

        if remove_dirs:
            try:
                logger.info('Removing domain directory for ' + vhost['name'])
                shutil.rmtree(os.path.join(user.info()[5] + '/domains/', vhost['name']), True)
            except OSError:
                pass

    basic.run_command('/usr/sbin/nginx -t')
    basic.run_command('/usr/sbin/nginx -s reload')
