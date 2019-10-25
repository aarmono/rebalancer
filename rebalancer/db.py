from os import path
from sqlite3 import connect

from .crypto import hash_user_token

def create_db_conn():
    this_file_path = path.abspath(__file__)
    this_dir = path.dirname(this_file_path)
    database_path = path.join(this_dir, "rebalance.db")

    conn = connect(database_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn
