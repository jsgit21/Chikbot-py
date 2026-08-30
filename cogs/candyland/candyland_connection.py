import pymysql

import database.db_methods as database

# Candyland event state lives in its own MySQL database on the server, not the
# shared Discord database. Everything else about the connection (the ~/.my.cnf
# credentials, autocommit) is the repo default from database.db_methods.
CANDYLAND_DATABASE = 'candyland'


def create_connection(cursor=pymysql.cursors.Cursor):
    return database.create_connection(database=CANDYLAND_DATABASE, cursor=cursor)
