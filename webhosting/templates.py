from jinja2 import Template, Environment, PackageLoader
import re

jinja_env = Environment(loader=PackageLoader('webhosting.library', 'templates'),
                        trim_blocks=True, lstrip_blocks=True)


def guess_autoescape(template_name):
    if template_name is None or '.' not in template_name:
        return False
    ext = template_name.rsplit('.', 1)[1]
    return ext in ('html', 'htm', 'xml')

# Custom filters
# http://jinja.pocoo.org/docs/api/#writing-filters
def strtosafe(unsafestr):
    return re.sub(r'[^a-zA-Z0-9]+', '', unsafestr)
jinja_env.filters['strtosafe'] = strtosafe

vhost_template = jinja_env.get_template('vhost.conf')
index_template = jinja_env.get_template('index.php')
php_ini_template = jinja_env.get_template('php/php.ini')
php_fpm_template = jinja_env.get_template('php/php-fpm.conf')
php_pool_template = jinja_env.get_template('php/pool.conf')
php_upstart_template = jinja_env.get_template('php/upstart.conf')

# Template designer documentation: http://jinja.pocoo.org/docs/templates/
