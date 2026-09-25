"""Create only the dedicated lab user. Run after Docker reports a healthy DB."""
import os
import re
from getpass import getpass
from pathlib import Path

import oracledb
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))
user = os.getenv('ORACLE_USER', 's1lab')
password = os.getenv('ORACLE_PASSWORD') or getpass('New lab user password: ')
admin_password = os.getenv('ORACLE_ADMIN_PASSWORD') or getpass('SYSTEM password: ')
if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,29}', user):
    raise ValueError('Use a simple Oracle username.')
if not re.fullmatch(r'[A-Za-z0-9_!#-]{12,100}', password):
    raise ValueError('Use 12–100 letters, digits, underscores, !, # or -.')
with oracledb.connect(user='system', password=admin_password,
                     dsn=os.getenv('ORACLE_DSN', '127.0.0.1:1535/FREEPDB1')) as db:
    with db.cursor() as cur:
        cur.execute('select count(*) from all_users where username=:1', [user.upper()])
        if cur.fetchone()[0]:
            print('Lab user already exists; password and data left unchanged.')
        else:
            cur.execute(f'CREATE USER {user} IDENTIFIED BY "{password}"')
            cur.execute(f'GRANT CREATE SESSION, CREATE TABLE TO {user}')
            cur.execute(f'ALTER USER {user} QUOTA 250M ON USERS')
            print('Created the isolated lab user with a 250 MB tablespace quota.')
