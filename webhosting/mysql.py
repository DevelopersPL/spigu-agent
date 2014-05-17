from __future__ import absolute_import
from celery import shared_task
from webhosting.library.database.mysql import MySQLManager
from webhosting.library.system.user import User

from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task(throws=(KeyError), bind=True)
def create(self, **UserOptions):
    user_obj = {'username': UserOptions['username']}
    user = User(user_obj)
    mm = MySQLManager()

    for db in UserOptions['mysqldbs']:
        dbname = user.username + '_' + db['name']
        if not mm.db_exists(dbname):
            mm.db_create(dbname, 'utf8')
            logger.info('Created database ' + dbname)

        privs = mm.privileges_unpack(dbname + '.*:ALL')
        if not mm.user_exists(dbname, '%'):
            mm.user_add(dbname, '%', db['password'], privs)
            logger.info('Created user %s @ %s', dbname, '%')
        else:
            mm.user_mod(dbname, '%', db['password'], privs)

@shared_task(throws=(KeyError), bind=True)
def delete(self, **UserOptions):
    user_obj = {'username': UserOptions['username']}
    user = User(user_obj)
    mm = MySQLManager()

    # delete all databases and users
    for db in UserOptions['mysqldbs']:
        dbname = user.username + '_' + db['name']
        if mm.db_exists(dbname):
            mm.db_delete(dbname)
            logger.info('Deleted database ' + dbname)

        if mm.user_exists(dbname, '%'):
            mm.user_delete(dbname, '%')
            logger.info('Deleted user %s@%s', dbname, '%')

@shared_task(throws=(KeyError), bind=True)
def userdelete(self, **UserOptions):
    user_obj = {'username': UserOptions['username']}
    user = User(user_obj)
    mm = MySQLManager()

    # delete all users
    for db in UserOptions['mysqldbs']:
        dbname = user.username + '_' + db['name']
        if mm.user_exists(dbname, '%'):
            mm.user_delete(dbname, '%')
            logger.info('Deleted user %s@%s', dbname, '%')
