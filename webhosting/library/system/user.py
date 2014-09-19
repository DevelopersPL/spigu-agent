import os
import pwd
import spwd
import grp
import shutil
import webhosting.library.system.group as group
import webhosting.library.basic as basic
from crypt import crypt

# This class is a representation of a real system account
class User(object):
    def __init__(self, params):
        self.uid = params.get('uid', None)
        self.non_unique = params.get('non_unique', False),
        self.comment = params.get('comment', None)
        self.username = params['username']                          # only field required - useful for deletion
        self.password = params.get('password', '')                  # password will be encrypted!
        self.password_login = params.get('password_login', True)
        self.expires = params.get('expires', None)
        self.shell = params.get('shell', None)
        self.group = params.get('group', None)                      # main group - usually automatic (same as username)
        self.groups_in = params.get('groups_in', [])                # groups in which user must be
        self.groups_out = params.get('groups_out', [])              # groups in which user must NOT be
        self.home = params.get('home', None)
        self.create_home = params.get('create_home', True)          # works for modify too -> ensures home exists
        self.system = params.get('system', False)                   # only works in create() !

    def exists(self):
        try:
            if pwd.getpwnam(self.username):
                return True
        except KeyError:
            return False

    def create(self):
        cmd = ['/usr/sbin/useradd']

        if self.uid is not None:
            cmd.append('-u')
            cmd.append(self.uid)

            if self.non_unique:
                cmd.append('-o')

        if self.comment is not None:
            cmd.append('-c')
            cmd.append(self.comment)

        # username is at the end ;)

        if self.password is not None:
            cmd.append('-p')
            cmd.append(self.encrypt_password())

        if self.expires is not None:
            cmd.append('-e')
            cmd.append(self.expires)

        if self.shell is not None:
            cmd.append('--shell')
            cmd.append(self.shell)

        if self.group is not None:
            if not group.exists(self.group):
                raise Exception("Group %s does not exist" % self.group)
            cmd.append('--gid')
            cmd.append(self.group)

        if self.groups_in is not None and len(self.groups_in):
            cmd.append('--groups')
            cmd.append(','.join(self.groups_in))

        # it's a new user, we don't handle groups_out here

        if self.home is not None:
            cmd.append('--home')
            cmd.append(self.home)

        if self.create_home:
            cmd.append('--create-home')
        else:
            cmd.append('-M')

        if self.system:
            cmd.append('-r')

        cmd.append(self.username)
        return basic.run_command(cmd)

    def info(self):
        """
        http://docs.python.org/dev/library/pwd.html
        returns tuple: name, password, uid, gid, gecos, home dir, shell
        """
        if not self.exists():
            return False
        info = list(pwd.getpwnam(self.username))
        if len(info[1]) == 1 or len(info[1]) == 0:
            try:
                info[1] = spwd.getspnam(self.username)[1]
            except KeyError:
                pass
        return info

    def pwd_info(self):
        """
        http://docs.python.org/dev/library/pwd.html
        """
        if not self.exists():
            return False
        return pwd.getpwnam(self.username)

    def shadow_info(self):
        """
        http://docs.python.org/dev/library/spwd.html
        returns tuple: name, password, day of last change, min, max, warn, inact, expire, flag
        """
        if not self.exists():
            return False
        info = list(spwd.getspnam(self.username))
        return info

    def get_current_groups(self):
        """
        Find additional groups in which user is a member
        Returns list of group names
        """
        groups = []
        info = self.info()
        for group in grp.getgrall():
            # skips user's primary group
            if self.username in group.gr_mem and not info[3] == group.gr_gid:
                groups.append(group[0])
        return groups

    def encrypt_password(self, salt=None):
        if salt is None:
            # If the salt is longer than 8 characters, crypt function puts newline at the end of salt, breaking usermod command
            salt = '$6$' + os.urandom(8).encode('base_64')[:8] + '$'

        ep = crypt(self.password, salt)

        if not self.password_login:
            ep = '!' + ep

        return ep

    def modify(self):
        cmd = ['/usr/sbin/usermod']
        info = self.info()
        shadow_info = self.shadow_info()

        if self.uid is not None and info[2] != int(self.uid):
            cmd.append('-u')
            cmd.append(self.uid)

            if self.non_unique:
                cmd.append('-o')

        if self.comment is not None and info[4] != self.comment:
            cmd.append('-c')
            cmd.append(self.comment)

        if self.password is not None:
            force_change = False
            try:
                salt = '$' + info[1].split("$")[1] + '$' + info[1].split("$")[2] + '$' # there is also [3] which we don't want
            except IndexError:
                # malformed encrypted password value - very rare
                force_change = True
            if force_change or info[1] != self.encrypt_password(salt):
                cmd.append('-p')
                cmd.append(self.encrypt_password())

        if self.expires is not None:
            if shadow_info[7] != self.expires and not (str(shadow_info[7]) == '-1' and self.expires == ''):
                cmd.append('-e')
                cmd.append(self.expires)

        if self.shell is not None and info[6] != self.shell:
            cmd.append('-s')
            cmd.append(self.shell)

        if self.group is not None:
            if not group.exists(self.group):
                raise Exception("Group %s does not exist" % self.group)
            ginfo = group.info(self.group)
            if info[3] != ginfo[2]:
                cmd.append('-g')
                cmd.append(self.group)

        if isinstance(self.groups_in, (list, tuple)) and isinstance(self.groups_out, (list, tuple)):
            current_groups = self.get_current_groups()
            groups = set(current_groups).union(self.groups_in).difference(self.groups_out)

            if groups != set(current_groups):
                cmd.append('-G')
                cmd.append(','.join(groups))
        else:
            raise Exception('groups_in or groups_out parameter in User class is not a list', self.groups_in, self.groups_out)

        if self.home is not None and info[5] != self.home:
            cmd.append('-m')
            cmd.append('-d')
            cmd.append(self.home)

        if self.create_home and len(info[5]) > 0:
            # Ensure home directory exists if the user somehow deleted it
            if not os.path.exists(info[5]):
            # use /etc/skel if possible
                if os.path.exists('/etc/skel'):
                    try:
                        shutil.copytree('/etc/skel', info[5], symlinks=True)
                    except OSError as e:
                        raise e
                else:
                    try:
                        os.makedirs(info[5])
                    except OSError as e:
                        raise e
            try:
                os.chown(info[5], info[2], info[3])
                for root, dirs, files in os.walk(info[5]):
                    for d in dirs:
                        os.chown(info[5], info[2], info[3])
                    for f in files:
                        if os.path.exists(f):
                            os.chown(os.path.join(root, f), info[2], info[3])
            except OSError as e:
                raise e

        # cannot change user type to "system" here

        # execute only if there is something to do
        if len(cmd) != 1:
            cmd.append(self.username)
            basic.run_command(cmd)

    def delete(self, signal='TERM'):
        # First kill user's processes
        cmd = ['/usr/bin/pkill']
        if signal is not None:
            cmd.append('--signal')
            cmd.append(signal)

        cmd.append('--euid')
        cmd.append(self.username)

        basic.run_command(cmd, check_rc=False)

        # Delete user now
        cmd = ['/usr/sbin/deluser']
        cmd.append('--remove-all-files')
        cmd.append(self.username)

        basic.run_command(cmd)

        # deluser is broken and does not delete symlinks
        basic.run_command('/bin/rm -rf /home/' + self.username)
