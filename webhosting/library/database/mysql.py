import os
import re
import ConfigParser
import MySQLdb
import webhosting.library.basic as basic

class MySQLManager:

    def __init__(self):
        mycnf_creds = self.load_mycnf()
        if mycnf_creds is False:
            login_user = "root"
            login_password = ""
        else:
            login_user = mycnf_creds["user"]
            login_password = mycnf_creds["passwd"]

        self.connection = MySQLdb.connect(user=login_user, passwd=login_password, db="mysql")

    def db_exists(self, db):
        res = self.connection.cursor().execute("SHOW DATABASES LIKE %s", (db,))
        return bool(res)

    def db_delete(self, db):
        query = "DROP DATABASE `%s`" % db
        self.connection.cursor().execute(query)
        return True

    def db_list(self):
        query = "SHOW DATABASES"
        cursor = self.connection.cursor()
        cursor.execute(query)
        dbs = []
        for db in cursor.fetchall():
            dbs.append(db[0])
        return dbs

    def db_dump(self, host, user, password, db_name, target, socket=None):
        cmd = basic.get_bin_path('mysqldump', True)
        cmd += " --quick --user=%s --password=%s" %(user, password)
        if socket is not None:
            cmd += " --socket=%s" % socket
        else:
            cmd += " --host=%s" % host
        cmd += " %s" % db_name
        if os.path.splitext(target)[-1] == '.gz':
            cmd = cmd + ' | gzip > ' + target
        elif os.path.splitext(target)[-1] == '.bz2':
            cmd = cmd + ' | bzip2 > ' + target
        else:
            cmd += " > %s" % target
        rc, stdout, stderr = basic.run_command(cmd)
        return rc, stdout, stderr

    def db_import(self, host, user, password, db_name, target, socket=None):
        cmd = basic.get_bin_path('mysql', True)
        cmd += " --user=%s --password=%s" %(user, password)
        if socket is not None:
            cmd += " --socket=%s" % socket
        else:
            cmd += " --host=%s" % host
        cmd += " -D %s" % db_name
        if os.path.splitext(target)[-1] == '.gz':
            cmd = 'gunzip < ' + target + ' | ' + cmd
        elif os.path.splitext(target)[-1] == '.bz2':
            cmd = 'bunzip2 < ' + target + ' | ' + cmd
        else:
            cmd += " < %s" % target
        rc, stdout, stderr = basic.run_command(cmd)
        return rc, stdout, stderr

    def db_create(self, db, encoding=None, collation=None):
        query = "CREATE DATABASE `%s`" % db
        if encoding is not None:
            query += " CHARACTER SET %s" % encoding
        if collation is not None:
            query += " COLLATE %s" % collation
        res = self.connection.cursor().execute(query)
        return True

    def user_find_like(self, like):
        cursor = self.connection.cursor()
        cursor.execute("SELECT User, Host FROM user WHERE user LIKE %s", like)
        return cursor.fetchall()

    def user_exists(self, user, host):
        cursor = self.connection.cursor()
        cursor.execute("SELECT count(*) FROM user WHERE user = %s AND host = %s", (user, host))
        count = cursor.fetchone()
        return count[0] > 0

    def user_add(self, user, host, password, new_priv):
        cursor = self.connection.cursor()
        cursor.execute("CREATE USER %s@%s IDENTIFIED BY %s", (user,host,password))
        if new_priv is not None:
            for db_table, priv in new_priv.iteritems():
                self.privileges_grant(user, host, db_table, priv)
        return True

    def user_mod(self, user, host, password, new_priv, append_privs=False):
        cursor = self.connection.cursor()
        changed = False
        grant_option = False

        # Handle passwords.
        if password is not None:
            cursor.execute("SELECT password FROM user WHERE user = %s AND host = %s", (user,host))
            current_pass_hash = cursor.fetchone()
            cursor.execute("SELECT PASSWORD(%s)", (password,))
            new_pass_hash = cursor.fetchone()
            if current_pass_hash[0] != new_pass_hash[0]:
                cursor.execute("SET PASSWORD FOR %s@%s = PASSWORD(%s)", (user,host,password))
                changed = True

        # Handle privileges.
        if new_priv is not None:
            curr_priv = self.privileges_get(user, host)

            # If the user has privileges on a db.table that doesn't appear at all in
            # the new specification, then revoke all privileges on it.
            for db_table, priv in curr_priv.iteritems():
                # If the user has the GRANT OPTION on a db.table, revoke it first.
                if "GRANT" in priv:
                    grant_option = True
                if db_table not in new_priv:
                    if user != "root" and "PROXY" not in priv and not append_privs:
                        self.privileges_revoke(user, host, db_table, grant_option)
                        changed = True

            # If the user doesn't currently have any privileges on a db.table, then
            # we can perform a straight grant operation.
            for db_table, priv in new_priv.iteritems():
                if db_table not in curr_priv:
                    self.privileges_grant(user, host, db_table, priv)
                    changed = True

            # If the db.table specification exists in both the user's current privileges
            # and in the new privileges, then we need to see if there's a difference.
            db_table_intersect = set(new_priv.keys()) & set(curr_priv.keys())
            for db_table in db_table_intersect:
                priv_diff = set(new_priv[db_table]) ^ set(curr_priv[db_table])
                if (len(priv_diff) > 0):
                    self.privileges_revoke(user, host, db_table, grant_option)
                    self.privileges_grant(user, host, db_table, new_priv[db_table])
                    changed = True

        return changed

    def user_delete(self, user, host):
        self.connection.cursor().execute("DROP USER %s@%s", (user, host))
        return True

    def privileges_get(self, user, host):
        """ MySQL doesn't have a better method of getting privileges aside from the
        SHOW GRANTS query syntax, which requires us to then parse the returned string.
        Here's an example of the string that is returned from MySQL:

         GRANT USAGE ON *.* TO 'user'@'localhost' IDENTIFIED BY 'pass';

        This function makes the query and returns a dictionary containing the results.
        The dictionary format is the same as that returned by privileges_unpack() below.
        """
        cursor = self.connection.cursor()
        output = {}
        cursor.execute("SHOW GRANTS FOR %s@%s", (user, host))
        grants = cursor.fetchall()

        def pick(x):
            if x == 'ALL PRIVILEGES':
                return 'ALL'
            else:
                return x

        for grant in grants:
            res = re.match("GRANT (.+) ON (.+) TO '.+'@'.+'( IDENTIFIED BY PASSWORD '.+')? ?(.*)", grant[0])
            if res is None:
                raise Exception("unable to parse the MySQL grant string")
            privileges = res.group(1).split(", ")
            privileges = [pick(x) for x in privileges]
            if "WITH GRANT OPTION" in res.group(4):
                privileges.append('GRANT')
            db = res.group(2)
            output[db] = privileges
        return output

    @staticmethod
    def privileges_unpack(priv):
        """ Take a privileges string, typically passed as a parameter, and unserialize
        it into a dictionary, the same format as privileges_get() above. We have this
        custom format to avoid using YAML/JSON strings inside YAML playbooks. Example
        of a privileges string:

         mydb.*:INSERT,UPDATE/anotherdb.*:SELECT/yetanother.*:ALL

        The privilege USAGE stands for no privileges, so we add that in on *.* if it's
        not specified in the string, as MySQL will always provide this by default.
        """
        output = {}
        for item in priv.split('/'):
            pieces = item.split(':')
            if pieces[0].find('.') != -1:
                pieces[0] = pieces[0].split('.')
                for idx, piece in enumerate(pieces):
                    if pieces[0][idx] != "*":
                        pieces[0][idx] = "`" + pieces[0][idx] + "`"
                pieces[0] = '.'.join(pieces[0])

            output[pieces[0]] = pieces[1].upper().split(',')

        if '*.*' not in output:
            output['*.*'] = ['USAGE']

        return output

    def privileges_revoke(self, user, host, db_table, grant_option):
        cursor = self.connection.cursor()
        if grant_option:
            query = "REVOKE GRANT OPTION ON %s FROM '%s'@'%s'" % (db_table,user,host)
            cursor.execute(query)
        query = "REVOKE ALL PRIVILEGES ON %s FROM '%s'@'%s'" % (db_table,user,host)
        cursor.execute(query)

    def privileges_grant(self, user, host, db_table, priv):
        cursor = self.connection.cursor()
        priv_string = ",".join(filter(lambda x: x != 'GRANT', priv))
        query = "GRANT %s ON %s TO '%s'@'%s'" % (priv_string,db_table,user,host)
        if 'GRANT' in priv:
            query = query + " WITH GRANT OPTION"
        cursor.execute(query)

    def strip_quotes(self, s):
        """ Remove surrounding single or double quotes

        >>> print strip_quotes('hello')
        hello
        >>> print strip_quotes('"hello"')
        hello
        >>> print strip_quotes("'hello'")
        hello
        >>> print strip_quotes("'hello")
        'hello

        """
        single_quote = "'"
        double_quote = '"'

        if s.startswith(single_quote) and s.endswith(single_quote):
            s = s.strip(single_quote)
        elif s.startswith(double_quote) and s.endswith(double_quote):
            s = s.strip(double_quote)
        return s

    def config_get(self, config, section, option):
        """ Calls ConfigParser.get and strips quotes

        See: http://dev.mysql.com/doc/refman/5.0/en/option-files.html
        """
        return self.strip_quotes(config.get(section, option))

    def load_mycnf(self):
        config = ConfigParser.RawConfigParser()
        mycnf = os.path.expanduser('~/.my.cnf')
        if not os.path.exists(mycnf):
            return False
        try:
            config.readfp(open(mycnf))
        except (IOError):
            raise
        # We support two forms of passwords in .my.cnf, both pass= and password=,
        # as these are both supported by MySQL.
        try:
            passwd = self.config_get(config, 'client', 'password')
        except (ConfigParser.NoOptionError):
            try:
                passwd = self.config_get(config, 'client', 'pass')
            except (ConfigParser.NoOptionError):
                return False
        try:
            creds = dict(user=self.config_get(config, 'client', 'user'), passwd=passwd)
        except (ConfigParser.NoOptionError):
            return False
        return creds