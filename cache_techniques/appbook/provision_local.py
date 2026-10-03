"""Provision a dedicated local Oracle cache lab schema, never an admin runtime.

Run explicitly: python provision_local.py --container acme-oracle-free
Only the randomly created cache lab credentials are saved, with mode 0600.
Anthropic credentials are never read or saved here.
"""
import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
path = ROOT / "data/oracle.json"
parser = argparse.ArgumentParser()
parser.add_argument("--container", required=True)
parser.add_argument("--dsn", default="127.0.0.1:1521/FREEPDB1")
args = parser.parse_args()
if path.exists():
    print("Dedicated cache lab connection already configured; keeping it.")
    raise SystemExit(0)
name = "CAB_" + secrets.token_hex(5).upper()
tbs = name + "_TS"
password = "A_" + secrets.token_hex(18)
sql = f'''WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SESSION SET CONTAINER=FREEPDB1;
CREATE TABLESPACE {tbs} DATAFILE '/opt/oracle/oradata/{tbs}.dbf' SIZE 16M AUTOEXTEND ON NEXT 16M MAXSIZE 256M;
CREATE USER {name} IDENTIFIED BY "{password}" DEFAULT TABLESPACE {tbs} QUOTA 256M ON {tbs};
GRANT CREATE SESSION, CREATE TABLE, CREATE SEQUENCE TO {name};
EXIT;
'''
result = subprocess.run(["docker", "exec", "-i", args.container, "sqlplus", "-s", "/", "as", "sysdba"], input=sql, text=True, capture_output=True, timeout=60)
if result.returncode:
    raise SystemExit(result.stdout.replace(password, "[redacted]") + result.stderr.replace(password, "[redacted]"))
path.parent.mkdir(exist_ok=True)
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as output:
    json.dump({"ORACLE_USER": name, "ORACLE_PASSWORD": password, "ORACLE_DSN": args.dsn}, output)
print("Created a dedicated appbook Oracle schema. Connection file is owner-readable only.")
