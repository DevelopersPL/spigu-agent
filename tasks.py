# -*- coding: utf-8 -*-
import os, shutil
import time
from agent import agent
from library.system.user import User
from celery.utils.log import get_task_logger
import library.basic
logger = get_task_logger(__name__)
from templates import vhost_template, index_template
import config
from lxml import etree
import library.basic as basic
from templates import strtosafe
import re
import ConfigParser
from library.database.mysql import MySQLManager as MySQLManager

@agent.task
def add(x, y):
    logger.info('Adding {0} + {1}'.format(x, y))
    logger.info('Waiting 10 seconds')
    time.sleep(10)
    return x + y

@agent.task(throws=(KeyError), bind=True)
def WebAccount(self, **AccountObject):
    #logger.info(repr(AccountObject))

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

        # XATTRs - allow www-data to access userdir
        # setfacl -m u:www-data:rX /home/web34/
        basic.run_command('/bin/setfacl -m u:www-data:rX /home/' + user.username)

        # Make sure domains directory exists
        library.basic.make_sure_path_exists(user.info()[5] + '/domains')
        os.chown(user.info()[5] + '/domains', user.info()[2], user.info()[3])
        os.chmod(user.info()[5] + '/domains', 0555)

    ############################### deal with vhosts ###############################
    # Delete all vhost configs
    existing_vhosts = os.listdir(config.LSWS_VHOST_DIR)
    for file in existing_vhosts:
        if re.compile('^' + user.username + '_(.*)\.xml$').match(file):
            os.remove(os.path.join(config.LSWS_VHOST_DIR, file))

    # load main LSWS config
    httpd_config = etree.parse(config.LSWS_CONFIG_PATH, etree.XMLParser(remove_blank_text=True))
    # print etree.tostring(httpd_config, pretty_print=True)

    # Unbind all vhost configs
    for virtualHost in httpd_config.find('virtualHostList').findall('virtualHost'):
        if re.compile('/'+user.username+'_(.*)\.xml$').match(virtualHost.find('configFile').text):
            httpd_config.find('virtualHostList').remove(virtualHost)

    if AccountObject['state'] not in ['suspended', 'deleted']:
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

            with open(user.info()[5] + '/domains/' + vhost['name'] + '/index.html', 'w') as vhost_file:
                vhost_file.write(index_template.render(vhost_data))
                vhost_file.close()
            os.chown(user.info()[5] + '/domains/' + vhost['name'] + '/index.html', user.info()[2], user.info()[3])
            os.chmod(user.info()[5] + '/domains/' + vhost['name'] + '/index.html', 0644)

            # look for the vhost in config and remove it
            # xpath("//virtualHostList/virtualHost[name='".$vhost['domain']."']")
            for virtualHost in httpd_config.find('virtualHostList').findall('virtualHost'):
                #logger.info('Name: ' + virtualHost.find('name').text)
                if virtualHost.find('name').text == vhost['name']:
                    httpd_config.find('virtualHostList').remove(virtualHost)
                    #logger.info("removing vhost")

            # look for listener and remove it
            # $lshttpd_config->xpath("//vhostMap[vhost='".$vhost['domain']."']")
            for listener in httpd_config.find('listenerList').findall('listener'):
                for mapping in listener.find('vhostMapList').findall('vhostMap'):
                    if mapping.find('vhost').text == vhost['name']:
                        listener.find('vhostMapList').remove(mapping)
                        #logger.info("removing vhost")

            # add new vhost to the config file
            newVH = etree.fromstring('''
            <virtualHost>
                <name></name>
                <vhRoot></vhRoot>
                <configFile></configFile>
                <note/>
                <allowSymbolLink>2</allowSymbolLink>
                <enableScript>1</enableScript>
                <restrained>1</restrained>
                <maxKeepAliveReq/>
                <smartKeepAlive>1</smartKeepAlive>
                <setUIDMode>2</setUIDMode>
                <chrootMode>0</chrootMode>
                <chrootPath/>
                <staticReqPerSec/>
                <dynReqPerSec/>
                <outBandwidth/>
                <inBandwidth/>
            </virtualHost>
            ''')
            newVH.find('name').text = vhost['name']
            newVH.find('vhRoot').text = user.info()[5] + '/domains/' + vhost['name']
            newVH.find('configFile').text = config.LSWS_VHOST_DIR + user.username + '_' + vhost['name'] + '.xml'
            newVH.find('note').text = user.username
            httpd_config.find('virtualHostList').append(newVH)

            # Add new vhost to the first listener available (this is stupid)
            # TODO: improve & SSL support
            newVHMapping = etree.fromstring('''
            <vhostMap>
              <vhost></vhost>
              <domain></domain>
            </vhostMap>
            ''')
            newVHMapping.find('vhost').text = vhost['name']
            newVHMapping.find('domain').text = ','.join(vhost['domains'])
            httpd_config.find('listenerList').find('listener').find('vhostMapList').append(newVHMapping)

    ##### Delete obsolete domain directories under /domains #####
    try:
        current_domain_dirs = os.listdir(user.info()[5] + '/domains/')
        valid_domain_dirs = []
        for vhost in AccountObject['vhosts']:
            valid_domain_dirs.append(vhost['name'])

        for directory in list(set(current_domain_dirs) - set(valid_domain_dirs)):
            logger.info('Removing obsolete domain directory: ' + directory)
            shutil.rmtree(os.path.join(user.info()[5] + '/domains/', directory), True)
    except OSError:
        pass

    ############################### deal with apps ###############################
    # look for all apps of this user and delete them
    for oldapp in httpd_config.find('extProcessorList').findall('extProcessor'):
        if re.compile('^' + user.username + '_').match(oldapp.find('name').text):
            httpd_config.find('extProcessorList').remove(oldapp)

    # look for all php ini dirs of this user and delete them
    for oldinidir in os.listdir('/opt/php/ini/'):
        if re.compile('^' + user.username + '_').match(oldinidir):
            shutil.rmtree(os.path.join('/opt/php/ini/', oldinidir), True)

    # add apps for this user
    if AccountObject['state'] not in ['suspended', 'deleted']:
        for app in AccountObject['apps']:
            if app['type'] != 'php':
                raise Exception('Unrecognized app type: ' + app['type'])

            newProcessor = etree.fromstring('''
            <extProcessor>
                <type>lsapi</type>
                <name>lsphp5_...</name>
                <address>uds://tmp/lshttpd/somethinghere.sock</address>
                <note/>
                <maxConns>10</maxConns>
                <env>PHP_LSAPI_MAX_REQUESTS=500</env>
                <env>PHP_LSAPI_CHILDREN=10</env>
                <env>LSAPI_AVOID_FORK=1</env>
                <env>LSAPI_MAX_IDLE=300</env>
                <env>LSAPI_ACCEPT_NOTIFY=0</env>
                <env>PHP_INI_SCAN_DIR=/opt/php/ini/''' + user.username + '_' + strtosafe(app['name']) + '''</env>
                <initTimeout>60</initTimeout>
                <retryTimeout>0</retryTimeout>
                <persistConn>1</persistConn>
                <pcKeepAliveTimeout/>
                <respBuffer>0</respBuffer>
                <autoStart>1</autoStart>
                <path>/opt/php/php-5.4.15/bin/lsphp</path>
                <backlog>10</backlog>
                <instances>1</instances>
                <extUser>someuser</extUser>
                <extGroup>somegrup</extGroup>
                <runOnStartUp/>
                <extMaxIdleTime>-1</extMaxIdleTime>
                <priority>0</priority>
                <memSoftLimit>6G</memSoftLimit>
                <memHardLimit>8G</memHardLimit>
                <procSoftLimit>800</procSoftLimit>
                <procHardLimit>1000</procHardLimit>
            </extProcessor>
            ''')

            newProcessor.find('name').text = user.username + '_' + strtosafe(app['name'])
            newProcessor.find('address').text = 'uds://tmp/lshttpd/lsphp5_' + user.username + '_' + strtosafe(app['name']) + '.sock'
            newProcessor.find('path').text = '/opt/php/php-5.5/bin/lsphp'
            newProcessor.find('extUser').text = user.username
            newProcessor.find('extGroup').text = user.username
            if not os.path.isfile('/opt/php/php-' + app['version'] + '/bin/lsphp'):
                raise Exception('PHP version ' + app['version'] + ' is not available on this server.')
            newProcessor.find('path').text = '/opt/php/php-' + app['version'] + '/bin/lsphp'
            httpd_config.find('extProcessorList').append(newProcessor)

            # install Pecl extensions

            # install PEAR stuff

            # Save php.ini
            library.basic.make_sure_path_exists('/opt/php/ini/' + user.username + '_' + strtosafe(app['name']))
            os.chown('/opt/php/ini/' + user.username + '_' + strtosafe(app['name']), 0, user.info()[3])
            os.chmod('/opt/php/ini/' + user.username + '_' + strtosafe(app['name']), 0750)
            ini = ConfigParser.ConfigParser()
            for setting in app['ini']:
                if setting['section'].upper() == 'DEFAULT':
                    setting['section'] = 'PHP'
                try:
                    ini.add_section(setting['section'])
                except DuplicateSectionError:
                    pass
                ini.set(setting['section'], setting['name'], setting['value'])

            with open('/opt/php/ini/' + user.username + '_' + strtosafe(app['name']) + '/php.ini', 'w') as inifile:
                    ini.write(inifile)

    #### End of LSWS operations ####
    # save global config
    httpd_config.write(config.LSWS_CONFIG_PATH, xml_declaration=True, pretty_print=True, encoding="UTF-8")
    # restart LSWS
    if os.path.isfile('/tmp/lshttpd/lshttpd.pid'):
        basic.run_command('/bin/kill -USR1 `/bin/cat /tmp/lshttpd/lshttpd.pid`')
    else:
        logger.warn('Not restarting LSWS - not running.')

    ############################### MySQL ###############################
    # deal with databases
    mm = MySQLManager()
    current_user_dbs = []
    for db in mm.db_list():
        if re.compile('^' + user.username + '_').match(db):
            current_user_dbs.append(db)

    user_dbs = []
    for db in AccountObject['mysqldbs']:
        user_dbs.append(user.username + '_' + db['name'])

    if AccountObject['state'] not in ['deleted']:
        dbs_to_delete = set(current_user_dbs) - set(user_dbs)
        for db in dbs_to_delete:
            mm.db_delete(db)
            logger.info('Deleted database ' + db)

        for db in AccountObject['mysqldbs']:
            if user.username+'_'+db['name'] not in current_user_dbs:
                mm.db_create(user.username + '_' + db['name'], 'utf8')
                logger.info('Creating database ' + db['name'])
    else:
        # delete all databases
        for db in current_user_dbs:
            mm.db_delete(db)
            logger.info('Deleted database ' + db)

    # deal with users
    current_user_users = mm.user_find_like(user.username + '_%') # ((user, host), (user, host)...)
    if AccountObject['state'] not in ['deleted']:
        for u in current_user_users:
            if u[0] not in user_dbs:
                mm.user_delete(u[0], u[1])
                logger.info('Deleted %s @ %s', (u[0], u[1]))

        for u in AccountObject['mysqldbs']:
            privs = mm.privileges_unpack(user.username + '_' + u['name'] + '.*:ALL')
            if not mm.user_exists(user.username + '_' + u['name'], ''):
                mm.user_add(user.username + '_' + u['name'], '', u['password'], privs)
            else:
                mm.user_mod(user.username + '_' + u['name'], '', u['password'], privs)
    else:
        for u in current_user_users:
            mm.user_delete(u[0], u[1])
            logger.info('Deleted %s @ %s', (u[0], u[1]))
