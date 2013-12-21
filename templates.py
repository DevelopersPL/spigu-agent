from jinja2 import Template, Environment, PackageLoader
jinja_env = Environment(loader=PackageLoader('library', 'templates'),
                        trim_blocks=True, lstrip_blocks=True)

def guess_autoescape(template_name):
    if template_name is None or '.' not in template_name:
        return False
    ext = template_name.rsplit('.', 1)[1]
    return ext in ('html', 'htm', 'xml')

vhost_template = jinja_env.get_template('vhost.xml')
