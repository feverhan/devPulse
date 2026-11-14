import json
import socket
import subprocess

import pymysql

print("--- pymysql \u8fde 127.0.0.1:3306 ---")
try:
    conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password="ztt123456", database="daylife", connect_timeout=8)
    with conn.cursor() as cur:
        cur.execute("select version(), database()")
        print("  \u8fde\u63a5\u6210\u529f\uff0c", cur.fetchone())
    conn.close()
except Exception as exc:
    print("  \u5931\u8d25\uff1a", exc)

print("--- redis PING ---")
try:
    with socket.create_connection(("127.0.0.1", 6379), timeout=8) as sock:
        sock.settimeout(8)
        sock.sendall(b"PING\r\n")
        print("  \u56de\u590d\uff1a", sock.recv(64))
except Exception as exc:
    print("  \u5931\u8d25\uff1a", exc)

info = json.loads(subprocess.run(["podman", "machine", "inspect", "podman-machine-default"], capture_output=True, text=True).stdout)
print("--- \u673a\u5668 IP ---")
print(json.dumps(info, ensure_ascii=False)[:600])
