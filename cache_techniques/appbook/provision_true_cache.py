"""Provision a dedicated application user for the Oracle True Cache pair, never an admin runtime.

Run explicitly after the primary and True Cache containers are healthy (see README):
    python provision_true_cache.py --container pri-db-free

Writes go to the primary service; reads go to the True Cache service, which replicates users and
data from the primary. Only the randomly created application credentials are saved, with mode 0600.
"""
import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
path = ROOT / "data/true_cache.json"
parser = argparse.ArgumentParser()
parser.add_argument("--container", default="pri-db-free")
parser.add_argument("--primary-dsn", default="127.0.0.1:1525/FREEPDB1")
parser.add_argument("--true-cache-dsn", default="127.0.0.1:1526/sales_pdb_tc")
args = parser.parse_args()
if path.exists():
    print("True Cache application connection already configured; keeping it.")
    raise SystemExit(0)
name = "TC_APP_" + secrets.token_hex(4).upper()
password = "A_" + secrets.token_hex(18)
sql = f'''WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SESSION SET CONTAINER=FREEPDB1;
CREATE USER {name} IDENTIFIED BY "{password}" DEFAULT TABLESPACE USERS QUOTA 256M ON USERS;
GRANT CREATE SESSION, CREATE TABLE TO {name};
EXIT;
'''
result = subprocess.run(["docker", "exec", "-i", args.container, "sqlplus", "-s", "/", "as", "sysdba"],
                        input=sql, text=True, capture_output=True, timeout=60)
if result.returncode:
    raise SystemExit(result.stdout.replace(password, "[redacted]") + result.stderr.replace(password, "[redacted]"))
path.parent.mkdir(exist_ok=True)
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as output:
    json.dump({"TRUE_CACHE_USER": name, "TRUE_CACHE_PASSWORD": password,
               "PRIMARY_DSN": args.primary_dsn, "TRUE_CACHE_DSN": args.true_cache_dsn}, output)
print(f"Created {name} on the primary. Connection file is owner-readable only.")
