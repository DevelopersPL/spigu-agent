from __future__ import absolute_import
from celery import shared_task
from webhosting.library.system.user import User
import webhosting.library.basic as basic
import webhosting.templates as templates

from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task(throws=(KeyError), bind=True)
def setup(self, **UserOptions):
    user_obj = {'username': UserOptions['username']}
    user = User(user_obj)

    basic.copytree('/etc/php5', '/home/' + user.username + '/.config/php5', symlinks=True)

    # So called environment for jinja2 template
    template_data = {
        "username": user.username,
        "homedir": user.info()[5],
    }

    with open('/home/' + user.username + '/.config/php5/fpm/php-fpm.conf', 'w') as f:
        f.write(templates.php_fpm_template.render(template_data))

    with open('/home/' + user.username + '/.config/php5/fpm/php.ini', 'w') as f:
        f.write(templates.php_ini_template.render(template_data))

    with open('/home/' + user.username + '/.config/php5/fpm/pool.d/www.conf', 'w') as f:
        f.write(templates.php_pool_template.render(template_data))

    basic.ensure_path('/home/' + user.username + '/.config/upstart')
    with open('/home/' + user.username + '/.config/upstart/php5-fpm.conf', 'w') as f:
        f.write(templates.php_upstart_template.render(template_data))

    basic.rec_chown(user.info()[5] + '/.config/php5', user.info()[2], user.info()[3])
    '''
    try:
        basic.run_command("XDG_RUNTIME_DIR=/run/user/`id -u "+user.username+"` UPSTART_SESSION=`initctl list-sessions | awk -F' ' '{ print $2 }'` restart php5-fpm", executable='/bin/bash')
    except Exception:
        basic.run_command("XDG_RUNTIME_DIR=/run/user/`id -u "+user.username+"` UPSTART_SESSION=`initctl list-sessions | awk -F' ' '{ print $2 }'` start php5-fpm", executable='/bin/bash')
    '''

    # stop PHP (and other daemons)
    try:
        basic.run_command('stop session-init USER=' + user.username, executable='/bin/bash')
    except Exception:
        pass

    # and start
    basic.run_command('start session-init USER=' + user.username, executable='/bin/bash')

    basic.run_command('/bin/setfacl -m u:www-data:rX /home/' + user.username + '/.cache')
