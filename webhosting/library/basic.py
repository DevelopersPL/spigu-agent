# Source: https://raw.github.com/ansible/ansible/devel/lib/ansible/module_utils/basic.py
# This code is (a modified) part of Ansible, but is an independent component.
# This particular file snippet, and this file snippet only, is BSD licensed.
# Modules you write using this snippet, which is embedded dynamically by Ansible
# still belong to the author of the module, and may assign their own license
# to the complete work.
#
# Copyright (c), Michael DeHaan <michael.dehaan@gmail.com>, 2012-2013
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

BOOLEANS_TRUE = ['yes', 'on', '1', 'true', 1]
BOOLEANS_FALSE = ['no', 'off', '0', 'false', 0]
BOOLEANS = BOOLEANS_TRUE + BOOLEANS_FALSE

import os
import subprocess
import sys
import types
import time
import shutil
import stat
import grp
import pwd
import errno


try:
    import json
except ImportError:
    try:
        import simplejson as json
    except ImportError:
        sys.stderr.write('Error: this requires a json module, none found!')
        sys.exit(1)
    except SyntaxError:
        sys.stderr.write('SyntaxError: probably due to json and python being for different versions')
        sys.exit(1)

HAVE_SELINUX=False
try:
    import selinux
    HAVE_SELINUX=True
except ImportError:
    pass

HAVE_HASHLIB=False
try:
    from hashlib import md5 as _md5
    HAVE_HASHLIB=True
except ImportError:
    from md5 import md5 as _md5

try:
    from hashlib import sha256 as _sha256
except ImportError:
    pass

try:
    from systemd import journal
    has_journal = True
except ImportError:
    import syslog
    has_journal = False


def user_and_group(self, filename):
    filename = os.path.expanduser(filename)
    st = os.lstat(filename)
    uid = st.st_uid
    gid = st.st_gid
    return (uid, gid)

def set_owner_if_different(self, path, owner, changed):
    path = os.path.expanduser(path)
    if owner is None:
        return changed
    orig_uid, orig_gid = self.user_and_group(path)
    try:
        uid = int(owner)
    except ValueError:
        try:
            uid = pwd.getpwnam(owner).pw_uid
        except KeyError:
            self.fail_json(path=path, msg='chown failed: failed to look up user %s' % owner)
    if orig_uid != uid:
        if self.check_mode:
            return True
        try:
            os.lchown(path, uid, -1)
        except OSError:
            self.fail_json(path=path, msg='chown failed')
        changed = True
    return changed

def set_group_if_different(self, path, group, changed):
    path = os.path.expanduser(path)
    if group is None:
        return changed
    orig_uid, orig_gid = self.user_and_group(path)
    try:
        gid = int(group)
    except ValueError:
        try:
            gid = grp.getgrnam(group).gr_gid
        except KeyError:
            self.fail_json(path=path, msg='chgrp failed: failed to look up group %s' % group)
    if orig_gid != gid:
        if self.check_mode:
            return True
        try:
            os.lchown(path, -1, gid)
        except OSError:
            self.fail_json(path=path, msg='chgrp failed')
        changed = True
    return changed

def set_mode_if_different(self, path, mode, changed):
    path = os.path.expanduser(path)
    if mode is None:
        return changed
    try:
        # FIXME: support English modes
        if not isinstance(mode, int):
            mode = int(mode, 8)
    except Exception, e:
        self.fail_json(path=path, msg='mode needs to be something octalish', details=str(e))

    st = os.lstat(path)
    prev_mode = stat.S_IMODE(st[stat.ST_MODE])

    if prev_mode != mode:
        if self.check_mode:
            return True
        # FIXME: comparison against string above will cause this to be executed
        # every time
        try:
            if 'lchmod' in dir(os):
                os.lchmod(path, mode)
            else:
                os.chmod(path, mode)
        except OSError, e:
            if os.path.islink(path) and e.errno == errno.EPERM:  # Can't set mode on symbolic links
                pass
            elif e.errno == errno.ENOENT: # Can't set mode on broken symbolic links
                pass
            else:
                raise e
        except Exception, e:
            self.fail_json(path=path, msg='chmod failed', details=str(e))

        st = os.lstat(path)
        new_mode = stat.S_IMODE(st[stat.ST_MODE])

        if new_mode != prev_mode:
            changed = True
    return changed

def set_file_attributes_if_different(self, file_args, changed):
    # set modes owners and context as needed
    changed = self.set_context_if_different(
        file_args['path'], file_args['secontext'], changed
    )
    changed = self.set_owner_if_different(
        file_args['path'], file_args['owner'], changed
    )
    changed = self.set_group_if_different(
        file_args['path'], file_args['group'], changed
    )
    changed = self.set_mode_if_different(
        file_args['path'], file_args['mode'], changed
    )
    return changed

def set_directory_attributes_if_different(self, file_args, changed):
    changed = self.set_context_if_different(
        file_args['path'], file_args['secontext'], changed
    )
    changed = self.set_owner_if_different(
        file_args['path'], file_args['owner'], changed
    )
    changed = self.set_group_if_different(
        file_args['path'], file_args['group'], changed
    )
    changed = self.set_mode_if_different(
        file_args['path'], file_args['mode'], changed
    )
    return changed

def add_path_info(self, kwargs):
    '''
    for results that are files, supplement the info about the file
    in the return path with stats about the file path.
    '''

    path = kwargs.get('path', kwargs.get('dest', None))
    if path is None:
        return kwargs
    if os.path.exists(path):
        (uid, gid) = self.user_and_group(path)
        kwargs['uid'] = uid
        kwargs['gid'] = gid
        try:
            user = pwd.getpwuid(uid)[0]
        except KeyError:
            user = str(uid)
        try:
            group = grp.getgrgid(gid)[0]
        except KeyError:
            group = str(gid)
        kwargs['owner'] = user
        kwargs['group'] = group
        st = os.lstat(path)
        kwargs['mode']  = oct(stat.S_IMODE(st[stat.ST_MODE]))
        # secontext not yet supported
        if os.path.islink(path):
            kwargs['state'] = 'link'
        elif os.path.isdir(path):
            kwargs['state'] = 'directory'
        elif os.stat(path).st_nlink > 1:
            kwargs['state'] = 'hard'
        else:
            kwargs['state'] = 'file'
        if HAVE_SELINUX and self.selinux_enabled():
            kwargs['secontext'] = ':'.join(self.selinux_context(path))
        kwargs['size'] = st[stat.ST_SIZE]
    else:
        kwargs['state'] = 'absent'
    return kwargs

def get_bin_path(self, arg, required=False, opt_dirs=[]):
    '''
    find system executable in PATH.
    Optional arguments:
       - required:  if executable is not found and required is true, fail_json
       - opt_dirs:  optional list of directories to search in addition to PATH
    if found return full path; otherwise return None
    '''
    sbin_paths = ['/sbin', '/usr/sbin', '/usr/local/sbin']
    paths = []
    for d in opt_dirs:
        if d is not None and os.path.exists(d):
            paths.append(d)
    paths += os.environ.get('PATH', '').split(os.pathsep)
    bin_path = None
    # mangle PATH to include /sbin dirs
    for p in sbin_paths:
        if p not in paths and os.path.exists(p):
            paths.append(p)
    for d in paths:
        path = os.path.join(d, arg)
        if os.path.exists(path) and self.is_executable(path):
            bin_path = path
            break
    if required and bin_path is None:
        self.fail_json(msg='Failed to find required executable %s' % arg)
    return bin_path

def boolean(self, arg):
    ''' return a bool for the arg '''
    if arg is None or type(arg) == bool:
        return arg
    if type(arg) in types.StringTypes:
        arg = arg.lower()
    if arg in BOOLEANS_TRUE:
        return True
    elif arg in BOOLEANS_FALSE:
        return False
    else:
        self.fail_json(msg='Boolean %s not in either boolean list' % arg)

def is_executable(self, path):
    '''is the given path executable?'''
    return (stat.S_IXUSR & os.stat(path)[stat.ST_MODE]
            or stat.S_IXGRP & os.stat(path)[stat.ST_MODE]
            or stat.S_IXOTH & os.stat(path)[stat.ST_MODE])

def digest_from_file(self, filename, digest_method):
    ''' Return hex digest of local file for a given digest_method, or None if file is not present. '''
    if not os.path.exists(filename):
        return None
    if os.path.isdir(filename):
        self.fail_json(msg="attempted to take checksum of directory: %s" % filename)
    digest = digest_method
    blocksize = 64 * 1024
    infile = open(filename, 'rb')
    block = infile.read(blocksize)
    while block:
        digest.update(block)
        block = infile.read(blocksize)
    infile.close()
    return digest.hexdigest()

def md5(self, filename):
    ''' Return MD5 hex digest of local file using digest_from_file(). '''
    return self.digest_from_file(filename, _md5())

def sha256(self, filename):
    ''' Return SHA-256 hex digest of local file using digest_from_file(). '''
    if not HAVE_HASHLIB:
        self.fail_json(msg="SHA-256 checksums require hashlib, which is available in Python 2.5 and higher")
    return self.digest_from_file(filename, _sha256())

def backup_local(self, fn):
    '''make a date-marked backup of the specified file, return True or False on success or failure'''
    # backups named basename-YYYY-MM-DD@HH:MM~
    ext = time.strftime("%Y-%m-%d@%H:%M~", time.localtime(time.time()))
    backupdest = '%s.%s' % (fn, ext)

    try:
        shutil.copy2(fn, backupdest)
    except shutil.Error, e:
        self.fail_json(msg='Could not make backup of %s to %s: %s' % (fn, backupdest, e))
    return backupdest

def cleanup(self,tmpfile):
    if os.path.exists(tmpfile):
        try:
            os.unlink(tmpfile)
        except OSError, e:
            sys.stderr.write("could not cleanup %s: %s" % (tmpfile, e))

def atomic_move(self, src, dest):
    '''atomically move src to dest, copying attributes from dest, returns true on success
    it uses os.rename to ensure this as it is an atomic operation, rest of the function is
    to work around limitations, corner cases and ensure selinux context is saved if possible'''
    context = None
    if os.path.exists(dest):
        try:
            st = os.stat(dest)
            os.chmod(src, st.st_mode & 07777)
            os.chown(src, st.st_uid, st.st_gid)
        except OSError, e:
            if e.errno != errno.EPERM:
                raise
        if self.selinux_enabled():
            context = self.selinux_context(dest)
    else:
        if self.selinux_enabled():
            context = self.selinux_default_context(dest)

    try:
        # Optimistically try a rename, solves some corner cases and can avoid useless work.
        os.rename(src, dest)
    except (IOError,OSError), e:
        # only try workarounds for errno 18 (cross device), 1 (not permited) and 13 (permission denied)
        if e.errno != errno.EPERM and e.errno != errno.EXDEV and e.errno != errno.EACCES:
            self.fail_json(msg='Could not replace file: %s to %s: %s' % (src, dest, e))

        dest_dir = os.path.dirname(dest)
        dest_file = os.path.basename(dest)
        tmp_dest = "%s/.%s.%s.%s" % (dest_dir,dest_file,os.getpid(),time.time())

        try: # leaves tmp file behind when sudo and  not root
            if os.getenv("SUDO_USER") and os.getuid() != 0:
                # cleanup will happen by 'rm' of tempdir
                shutil.copy(src, tmp_dest)
            else:
                shutil.move(src, tmp_dest)
            if self.selinux_enabled():
                self.set_context_if_different(tmp_dest, context, False)
            os.rename(tmp_dest, dest)
        except (shutil.Error, OSError, IOError), e:
            self.cleanup(tmp_dest)
            self.fail_json(msg='Could not replace file: %s to %s: %s' % (src, dest, e))

    if self.selinux_enabled():
        # rename might not preserve context
        self.set_context_if_different(dest, context, False)


def run_command(args, check_rc=True, close_fds=False, executable=None, data=None, binary_data=False, path_prefix=None):
    '''
    Execute a command, returns rc, stdout, and stderr.
    args is the command to run
    If args is a list, the command will be run with shell=False.
    Otherwise, the command will be run with shell=True when args is a string.
    Other arguments:
    - check_rc (boolean)  Whether to raise Exception in case of
                          non zero RC.  Default is True.
    - close_fds (boolean) See documentation for subprocess.Popen().
                          Default is False.
    - executable (string) See documentation for subprocess.Popen().
                          Default is None.
    '''
    if isinstance(args, list):
        shell = False
        print 'Running command: ' + ' '.join(args)
    elif isinstance(args, basestring):
        shell = True
        print 'Running command: ' + args
    else:
        raise Exception("Argument 'args' to run_command must be list or string")
    rc = 0
    msg = None
    st_in = None

    # Set a temporary env path if a prefix is passed
    env=os.environ
    if path_prefix:
        env['PATH']="%s:%s" % (path_prefix, env['PATH'])

    if data:
        st_in = subprocess.PIPE
    try:
        if path_prefix is not None:
            cmd = subprocess.Popen(args,
                                   executable=executable,
                                   shell=shell,
                                   close_fds=close_fds,
                                   stdin=st_in,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   env=env)
        else:
            cmd = subprocess.Popen(args,
                                   executable=executable,
                                   shell=shell,
                                   close_fds=close_fds,
                                   stdin=st_in,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)

        if data:
            if not binary_data:
                data += '\\n'
        out, err = cmd.communicate(input=data)
        rc = cmd.returncode
    except (OSError, IOError), e:
        raise

    if rc != 0 and check_rc:
        msg = err.rstrip()
        raise Exception('Command ' + ' '.join(args) + ' returned error code ' + str(rc) + ' with message "' + msg + '"')
    return (rc, out, err)

def pretty_bytes(size):
    ranges = (
            (1<<70L, 'ZB'),
            (1<<60L, 'EB'),
            (1<<50L, 'PB'),
            (1<<40L, 'TB'),
            (1<<30L, 'GB'),
            (1<<20L, 'MB'),
            (1<<10L, 'KB'),
            (1, 'Bytes')
        )
    for limit, suffix in ranges:
        if size >= limit:
            break
    return '%.2f %s' % (float(size)/ limit, suffix)

def ensure_path(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def copytree(src, dst, symlinks=False, ignore=None):
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    ensure_path(dst)
    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                if os.path.exists(dstname):
                    os.remove(dstname)
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, ignore)
            else:
                if os.path.exists(dstname):
                    os.remove(dstname)
                shutil.copy2(srcname, dstname)
            # XXX What about devices, sockets etc.?
        except (IOError, os.error) as why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except shutil.Error as err:
            errors.extend(err.args[0])
    try:
        shutil.copystat(src, dst)
    except WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError as why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise shutil.Error(errors)

def rec_chown(path, uid, gid):
        os.chown(path, uid, gid)
        for item in os.listdir(path):
            try:
                itempath = os.path.join(path, item)
            except UnicodeDecodeError:
                continue
            if os.path.islink(itempath):
                continue
            elif os.path.isfile(itempath):
                os.chown(itempath, uid, gid)
            elif os.path.isdir(itempath):
                os.chown(itempath, uid, gid)
                rec_chown(itempath, uid, gid)
