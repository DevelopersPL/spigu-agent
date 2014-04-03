#!/usr/bin/python
"""
To use this to mimic the EC2 metadata service entirely, run it like:
  # where 'eth0' is *some* interface.  if i used 'lo:0' i got 5 second or so delays on response.
  sudo ifconfig eth0:0 169.254.169.254 netmask 255.255.255.255

  sudo ./mdserv 169.254.169.254:80
Then:
  wget -q http://169.254.169.254/latest/meta-data/instance-id -O -; echo
  curl --silent http://169.254.169.254/latest/meta-data/instance-id ; echo
  ec2metadata --instance-id

DOCS: http://cloudinit.readthedocs.org/en/latest/topics/examples.html#run-commands-on-first-boot
"""

import sys
import BaseHTTPServer
import requests
import yaml
import json

# output of: python -c 'import boto.utils; boto.utils.get_instance_metadata()'
md = {
    'instance-action': 'none',
    'instance-id': '',
    'profile': 'default-paravirtual',
    'public-keys': {
        'brickies': [
            'ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAgEAv4JC+b8Oy97Sf6+egMXVQi9yySZrAC0lBeu3ByyL+qAyqzH6OfPFNcPlbVgTBGtRTF4ioiqcMKqgn9RXjsmNzbUjkLqTaycDHk5cyYsf8hpzPyYj9sBtX5mWeeqr2JnOd8ZvXkYfawySE79sMe8yfioLtFclGRWMaaWsnmAUt1V1Egg3k0WlpwWr43/JKt05s0vS/lIXS7FnqmTHZ1dTCmf3jm3ayoqfllwvbNGN5IuZ3uf6Zem0ferzB7vPEph7Y6jlI47f3hdIvpLrK1OoiTGAUI+4/oUjIVTiRtC7hWBhRjwDt/+aIVohDFIwgf4H/4HmLWOKgxIilxSlINyVF9EWGfx0t9AJSIvdzyHHYlC9Ekan5dT6uPSR+nDZxoUszj/UAaPkld5dRgB1vWVPnlRYwJ9eLgg8T04ypfxmw2v8fI/Kwe9/9LIOpMuNVKB1tblWTC623/aYF7SxAQCi+80Q4R5B3bM5OuHrRQOe/NI10UEgLBv12xrp3RISXHAUHY0c+ZOZJ6mntjo0dbpKqvGEngoJDRQ4jQ9YwiUKuF58B/s5y6IgNpu5n6ig4P5N39f1zt0rgnKtXR2D/sip6RzHS6paEyQdMgXbPcgYr5e3ep+0HX+gtDp5PcZKCj713CW/Dg9L6DaZJqy97/QKPY/k1Tnorap7KflfJn4oPZU= root@hn.dondaniello.com',
            ''
        ]
    }
}

ud = yaml.load("""#cloud-config
#
# This is an example file to automatically configure resolv.conf when the
# instance boots for the first time.
#
# Ensure that your yaml is valid and pass this as user-data when starting
# the instance. Also be sure that your cloud.cfg file includes this
# configuration module in the appropirate section.
#
manage-resolv-conf: true

resolv_conf:
  nameservers: ['8.8.4.4', '8.8.8.8']
  options:
    rotate: true
    timeout: 1

users:
  - name: otsmanager
    gecos: OTS Manager
    lock-passwd: false
#    passwd: $6$rounds=4096$h6LqwhzGpH$EpvFiqxSf5VskNbSDVXULIGSNJHRoY.mW3cEkvw/.vbIrY0vJN71EkOc1QAXtMlZEV078UJUUKaSDwHNuWusV0
#    sudo: "ALL=(ALL) NOPASSWD:ALL"

# phone_home: if this dictionary is present, then the phone_home
# cloud-config module will post specified data back to the given
# url
# default: none
# phone_home:
#  url: http://my.foo.bar/$INSTANCE/
#  post: all
#  tries: 10
#
phone_home:
  url: https://spigu.net/api/otshosting/phone
  post: all
  tries: 10

disable_root: true
ssh_pwauth: True

# Upgrade the instance on first boot
# (ie run apt-get upgrade)
#
# Default: false
# Aliases: apt_upgrade
package_upgrade: true

apt_mirror: http://mirror.ovh.net/ubuntu/

package_update: true
package_upgrade: true

apt_sources:
- source: "ppa:rquillo/ansible"
- source: deb $MIRROR $RELEASE restricted multiverse
- source: deb $MIRROR $RELEASE-updates restricted multiverse
- source: deb $MIRROR $RELEASE-security restricted multiverse

packages:
 - python-paramiko
 - python-yaml
 - python-jinja2
 - python-simplejson
 - git
 - ansible

# final_message
# default: cloud-init boot finished at $TIMESTAMP. Up $UPTIME seconds
# this message is written by cloud-final when the system is finished
# its first boot
final_message: "The system is finally up, after $uptime seconds"

# run commands
# default: none
# runcmd contains a list of either lists or a string
# each item will be executed in order at rc.local like level with
# output to the console
# - if the item is a list, the items will be properly executed as if
#   passed to execve(3) (with the first arg as the command).
# - if the item is a string, it will be simply written to the file and
#   will be interpreted by 'sh'
#
# Note, that the list has to be proper yaml, so you have to escape
# any characters yaml would eat (':' can be problematic)
runcmd:
  - 'echo "localhost" > /tmp/ansible_hosts'
  - 'export ANSIBLE_HOSTS=/tmp/ansible_hosts'
  - 'ansible-pull -U https://github.com/DSpeichert/otshosting-provisioning.git -d /srv/otshosting-provisioning'

""")

def MD_TREE():
    return {
        'latest': {'user-data': "#cloud-config\n" + yaml.dump(ud), 'meta-data': md},
        '2009-04-04': {'user-data': "#cloud-config\n" + yaml.dump(ud), 'meta-data': md},
        '2011-01-01': {'user-data': "#cloud-config\n" + yaml.dump(ud), 'meta-data': md},
    }

def fixup_pubkeys(pk_dict, listing):
    # if pk_dict is a public-keys dictionary as returned by boto
    # listing is boolean indicating if this is a listing or a item
    #
    # public-keys is messed up. a list of /latest/meta-data/public-keys/
    # shows something like: '0=brickies'
    # but a GET to /latest/meta-data/public-keys/0=brickies will fail
    # you have to know to get '/latest/meta-data/public-keys/0', then
    # from there you get a 'openssh-key', which you can get.
    # this hunk of code just re-works the object for that.
    i = -1
    mod_cur = {}
    for k in sorted(pk_dict.keys()):
        i = i + 1
        if listing:
            mod_cur["%d=%s" % (i, k)] = ""
        else:
            mod_cur["%d" % i] = {"openssh-key": '\n'.join(pk_dict[k])}
    return (mod_cur)


class myRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):

        # set 'path' to "normalized" path, ie without leading
        # or trailing '/' and without double /
        toks = [i for i in self.path.split("/") if i != ""]
        path = '/'.join(toks)

        try:
            response = requests.get('https://spigu.net/api/otshosting/' + self.client_address[0])
            try:
                result = response.json()
            except TypeError:
                result = json.loads(response.text)
            md['instance-id'] = str(result['instance_id'])
            ud['users'][0]['plain_text_passwd'] = str(result['password'])
        except Exception, e:
            print e.message
            self.send_response(500)
            self.end_headers()
            return

        cur = MD_TREE()

        for tok in toks:
            if isinstance(cur, str):
                cur = None
                break
            cur = cur.get(tok, None)
            if cur == None:
                break
            if tok == "public-keys":
                cur = fixup_pubkeys(cur, toks[-1] == "public-keys")

        if cur == None:
            output = None
        elif isinstance(cur, str):
            output = cur
        else:
            mlist = []
            for k in sorted(cur.keys()):
                if isinstance(cur[k], str):
                    mlist.append(k)
                else:
                    mlist.append("%s/" % k)

            output = "\n".join(mlist)

        if cur:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(output)
        else:
            self.send_response(404)
            self.end_headers()

        return

    def do_POST(self):
        return


def run_while_true(server_class=BaseHTTPServer.HTTPServer,
                   handler_class=BaseHTTPServer.BaseHTTPRequestHandler,
                   port=80, ipaddr='169.254.169.254'):
    """
    This assumes that keep_running() is a function of no arguments which
    is tested initially and after each request.  If its return value
    is true, the server continues.
    """
    server_address = (ipaddr, int(port))
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()


args = {}
args['handler_class'] = myRequestHandler
args['port'] = 80
args['ipaddr'] = '169.254.169.254'
if len(sys.argv) == 2:
    toks = sys.argv[1].split(":")
    if len(toks) == 1:
        # port only
        args['port'] = sys.argv[1]
    if len(toks) == 2:
        # host:port
        (args['ipaddr'], args['port']) = toks

print "listening on %s:%s" % (args['ipaddr'], args['port'])
run_while_true(**args)
