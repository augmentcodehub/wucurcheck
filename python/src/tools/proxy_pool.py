#!/usr/bin/env python3
"""
Proxy Pool — 从订阅链接生成 sing-box 多端口配置并启动
支持 sing-box JSON 格式和 vless/hysteria2 URI 格式

用法:
  python proxy_pool.py start   # 启动代理池
  python proxy_pool.py list    # 列出可用代理
  python proxy_pool.py stop    # 停止代理池
  python proxy_pool.py test    # 测试代理连通性
"""

import base64
import json
import os
import signal
import subprocess
import sys
import urllib.parse
import urllib.request
import ssl
from pathlib import Path

SUBSCRIPTIONS = [
    os.environ.get("PROXY_SUB_1", "https://app.mitce.net/?sid=248117&token=srvpksca&app=sb_112"),
    os.environ.get("PROXY_SUB_2", "https://43.139.248.121:9000/hxyunvip?token=bcbb2b4c74523689afea6adb2f4ea8e5"),
]

BASE_PORT = 11000
SING_BOX_BIN = Path(__file__).parent / "sing-box"
CONFIG_PATH = Path(__file__).parent / "proxy-pool-config.json"
PID_FILE = Path(__file__).parent / "proxy-pool.pid"
PROXIES_FILE = Path(__file__).parent / "proxy-pool-list.json"


def fetch_url(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "sing-box"})
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        return resp.read()


def parse_singbox_json(data):
    """解析 sing-box JSON 格式订阅"""
    config = json.loads(data)
    outbounds = config.get("outbounds", [])
    skip_types = {"direct", "block", "dns", "selector", "urltest"}
    return [o for o in outbounds if o.get("type") not in skip_types]


def parse_vless_uri(uri):
    """解析 vless:// URI 为 sing-box outbound"""
    rest = uri[8:]  # remove vless://
    main, name = rest.rsplit("#", 1) if "#" in rest else (rest, "unknown")
    name = urllib.parse.unquote(name).strip()
    userinfo_host, params_str = main.split("?", 1) if "?" in main else (main, "")
    uuid, server_port = userinfo_host.split("@", 1)
    server, port = server_port.rsplit(":", 1)
    params = dict(urllib.parse.parse_qsl(params_str))

    outbound = {
        "type": "vless",
        "tag": name,
        "server": server,
        "server_port": int(port),
        "uuid": uuid,
        "flow": params.get("flow", ""),
    }

    # TLS / Reality
    security = params.get("security", "")
    if security == "reality":
        outbound["tls"] = {
            "enabled": True,
            "server_name": params.get("sni", ""),
            "utls": {"enabled": True, "fingerprint": params.get("fp", "chrome")},
            "reality": {
                "enabled": True,
                "public_key": params.get("pbk", ""),
                "short_id": params.get("sid", ""),
            },
        }
    elif security == "tls":
        outbound["tls"] = {
            "enabled": True,
            "server_name": params.get("sni", ""),
            "utls": {"enabled": True, "fingerprint": params.get("fp", "chrome")},
        }

    # Transport
    net_type = params.get("type", "tcp")
    if net_type == "grpc":
        outbound["transport"] = {
            "type": "grpc",
            "service_name": params.get("serviceName", ""),
        }
    elif net_type == "ws":
        outbound["transport"] = {
            "type": "ws",
            "path": urllib.parse.unquote(params.get("path", "/")),
            "headers": {"Host": params.get("host", "")},
        }

    return outbound


def parse_hysteria2_uri(uri):
    """解析 hysteria2:// URI 为 sing-box outbound"""
    rest = uri[12:]  # remove hysteria2://
    main, name = rest.rsplit("#", 1) if "#" in rest else (rest, "unknown")
    name = urllib.parse.unquote(name).strip()

    # uuid:password@server:port/?params or uuid@server:port/?params
    if "?" in main:
        host_part, params_str = main.split("?", 1)
    else:
        host_part, params_str = main, ""
    params = dict(urllib.parse.parse_qsl(params_str.lstrip("/")))

    if "@" in host_part:
        auth, server_port = host_part.rsplit("@", 1)
        # auth might be uuid:password or just uuid
        password = auth.split(":", 1)[0] if ":" not in auth else auth
    else:
        server_port = host_part
        password = ""

    server, port = server_port.rsplit(":", 1)
    port = int(port.rstrip("/"))

    outbound = {
        "type": "hysteria2",
        "tag": name,
        "server": server,
        "server_port": port,
        "password": password,
        "tls": {
            "enabled": True,
            "server_name": params.get("sni", server),
            "insecure": params.get("insecure", "0") == "1",
        },
    }

    if params.get("obfs"):
        outbound["obfs"] = {
            "type": params["obfs"],
            "password": params.get("obfs-password", ""),
        }

    return outbound


def parse_uri_list(data):
    """解析 base64 编码的 URI 列表"""
    try:
        text = base64.b64decode(data).decode("utf-8")
    except Exception:
        text = data.decode("utf-8") if isinstance(data, bytes) else data

    nodes = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if line.startswith("vless://"):
            try:
                nodes.append(parse_vless_uri(line))
            except Exception:
                pass
        elif line.startswith("hysteria2://"):
            try:
                nodes.append(parse_hysteria2_uri(line))
            except Exception:
                pass
        # Skip ss://, tuic:// etc for now
    return nodes


def fetch_all_nodes():
    """从所有订阅获取节点"""
    all_nodes = []
    for url in SUBSCRIPTIONS:
        if not url:
            continue
        try:
            data = fetch_url(url)
            # Try sing-box JSON first
            try:
                nodes = parse_singbox_json(data)
                print(f"  [sing-box] {url[:50]}... → {len(nodes)} 节点")
            except (json.JSONDecodeError, KeyError):
                nodes = parse_uri_list(data)
                print(f"  [URI list] {url[:50]}... → {len(nodes)} 节点")
            all_nodes.extend(nodes)
        except Exception as e:
            print(f"  [ERROR] {url[:50]}... → {e}")
    return all_nodes


def generate_config(nodes):
    """生成 sing-box 配置"""
    inbounds = []
    outbounds = []
    proxy_list = []

    for i, node in enumerate(nodes):
        port = BASE_PORT + i
        tag = node.get("tag", f"node-{i}")
        # Deduplicate tags
        tag = f"{tag}-{i}" if any(n.get("tag") == tag for n in outbounds) else tag
        inbound_tag = f"in-{i}"

        inbounds.append({
            "type": "mixed",
            "tag": inbound_tag,
            "listen": "127.0.0.1",
            "listen_port": port,
        })

        node["tag"] = tag
        outbounds.append(node)

        proxy_list.append({
            "tag": tag,
            "port": port,
            "proxy": f"socks5://127.0.0.1:{port}",
            "inbound_tag": inbound_tag,
        })

    outbounds.append({"type": "direct", "tag": "direct"})

    rules = [{"inbound": [p["inbound_tag"]], "outbound": p["tag"]} for p in proxy_list]

    config = {
        "log": {"level": "error"},
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {"rules": rules, "final": "direct"},
    }
    return config, proxy_list


def start():
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"代理池已在运行 (PID: {pid})")
            return
        except OSError:
            PID_FILE.unlink()

    print("获取订阅...")
    nodes = fetch_all_nodes()
    if not nodes:
        print("❌ 没有获取到任何节点")
        return
    print(f"共 {len(nodes)} 个节点")

    print("生成配置...")
    config, proxy_list = generate_config(nodes)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    PROXIES_FILE.write_text(json.dumps(proxy_list, indent=2, ensure_ascii=False))

    print(f"启动 sing-box（端口 {BASE_PORT}-{BASE_PORT + len(nodes) - 1}）...")
    proc = subprocess.Popen(
        [str(SING_BOX_BIN), "run", "-c", str(CONFIG_PATH)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    import time
    time.sleep(2)
    if proc.poll() is not None:
        err = proc.stderr.read().decode()
        print(f"❌ 启动失败:\n{err[:500]}")
        return

    PID_FILE.write_text(str(proc.pid))
    print(f"✅ 代理池已启动 (PID: {proc.pid})")
    print(f"   共 {len(proxy_list)} 个代理，端口 {BASE_PORT}-{BASE_PORT + len(proxy_list) - 1}")
    print(f"\n   示例: curl -x socks5://127.0.0.1:{BASE_PORT} http://httpbin.org/ip")


def stop():
    if not PID_FILE.exists():
        print("代理池未运行")
        return
    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"✅ 已停止 (PID: {pid})")
    except OSError:
        print("进程已不存在")
    PID_FILE.unlink(missing_ok=True)


def list_proxies():
    if not PROXIES_FILE.exists():
        print("代理池未启动")
        return
    proxies = json.loads(PROXIES_FILE.read_text())
    print(f"共 {len(proxies)} 个代理:\n")
    for p in proxies:
        print(f"  {p['tag']:30s} → {p['proxy']}")


def test():
    if not PROXIES_FILE.exists():
        print("代理池未启动")
        return
    proxies = json.loads(PROXIES_FILE.read_text())
    print(f"测试前 15 个代理...\n")

    ok = 0
    for p in proxies[:15]:
        try:
            result = subprocess.run(
                ["curl", "-s", "--connect-timeout", "5", "-x", p["proxy"], "http://httpbin.org/ip"],
                capture_output=True, text=True, timeout=8
            )
            if "origin" in result.stdout:
                ip = json.loads(result.stdout)["origin"]
                print(f"  ✅ {p['tag']:30s} → {ip}")
                ok += 1
            else:
                print(f"  ❌ {p['tag']:30s}")
        except Exception:
            print(f"  ❌ {p['tag']:30s} (超时)")

    print(f"\n结果: {ok}/{min(len(proxies), 15)} 可用")


def get_proxies():
    """供其他程序调用"""
    if not PROXIES_FILE.exists():
        return []
    return json.loads(PROXIES_FILE.read_text())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    {"start": start, "stop": stop, "list": list_proxies, "test": test}.get(cmd, lambda: print(__doc__))()
