# Proxy Pool 使用教程

## 概述

`proxy_pool.py` 是一个本地代理池工具，从 VPN 订阅链接解析节点，通过 sing-box 为每个节点开一个本地 SOCKS5 端口。Python 程序可以通过不同端口使用不同出口 IP，实现 IP 轮换。

## 文件位置

```
/home/administrator/proxy_pool.py      # 主程序
/home/administrator/sing-box           # sing-box 二进制
/home/administrator/proxy-pool-list.json   # 可用代理列表（启动后生成）
/home/administrator/proxy-pool-config.json # sing-box 配置（自动生成）
/home/administrator/proxy-pool.pid     # 进程 PID
```

## 基本命令

```bash
cd /home/administrator

# 启动代理池
python3 proxy_pool.py start

# 查看可用代理列表
python3 proxy_pool.py list

# 测试代理连通性
python3 proxy_pool.py test

# 停止代理池
python3 proxy_pool.py stop
```

## 启动输出示例

```
获取订阅...
  [sing-box] https://app.mitce.net/... → 43 节点
  [URI list] https://43.139.248.121/... → 69 节点
共 112 个节点
启动 sing-box（端口 11000-11111）...
✅ 代理池已启动 (PID: 152651)
```

## 在 Python 中使用

### 方式 1：直接用 httpx + proxy 参数

```python
import httpx

# 创建带代理的 client
client = httpx.Client(proxy="socks5://127.0.0.1:11000", timeout=30)
response = client.get("http://httpbin.org/ip")
print(response.json())  # {"origin": "18.163.187.140"}
client.close()
```

### 方式 2：轮换多个代理

```python
import httpx
import json

# 读取可用代理列表
proxies = json.load(open("/home/administrator/proxy-pool-list.json"))

# 每次请求用不同代理
for i, task in enumerate(tasks):
    proxy_url = proxies[i % len(proxies)]["proxy"]
    client = httpx.Client(proxy=proxy_url, timeout=30)
    # ... 执行请求 ...
    client.close()
```

### 方式 3：导入 get_proxies() 函数

```python
import sys
sys.path.insert(0, "/home/administrator")
from proxy_pool import get_proxies

proxies = get_proxies()
# proxies = [{"tag": "HK-1", "port": 11000, "proxy": "socks5://127.0.0.1:11000"}, ...]
```

## 在 wucurcheck 注册中使用

```python
import httpx
import json
from adapters.http.wucur_client import register_account

proxies = json.load(open("/home/administrator/proxy-pool-list.json"))
available = [p["proxy"] for p in proxies if "HK" in p["tag"]]  # 只用 HK 节点

for i, account in enumerate(accounts):
    proxy = available[i % len(available)]
    client = httpx.Client(http2=True, timeout=30, proxy=proxy)
    result = register_account(client, account["username"], account["password"])
    client.close()
    time.sleep(3)  # 短间隔即可，IP 不同不会被限流
```

## 前置依赖

```bash
# httpx 需要 socksio 才能用 SOCKS5 代理
cd /home/administrator/workspace/open-source/wucurcheck
uv add socksio
```

## 订阅配置

支持两种订阅格式：

1. **sing-box JSON**（推荐）：URL 带 `app=sb_112` 参数
2. **V2ray URI 列表**：base64 编码的 vless:// / hysteria2:// 链接

通过环境变量或直接修改 `proxy_pool.py` 中的 `SUBSCRIPTIONS` 列表配置：

```python
SUBSCRIPTIONS = [
    "https://your-provider.com/?token=xxx&app=sb_112",
    "https://another-provider.com/?token=yyy",
]
```

## 支持的协议

| 协议 | 格式 | 状态 |
|------|------|------|
| vless + reality + gRPC | sing-box JSON | ✅ 可用 |
| vless + reality + tcp | URI 解析 | ✅ 已支持（需节点可用） |
| hysteria2 | sing-box JSON / URI | ✅ 已支持（WSL 下 UDP 可能不通） |
| shadowsocks | sing-box JSON | ✅ 可用 |
| tuic | sing-box JSON | ⚠️ UDP 依赖，WSL 下可能不通 |

## 注意事项

1. **不影响 Windows**：sing-box 跑在 WSL 的 127.0.0.1，不动 Windows 任何配置
2. **端口范围**：默认从 11000 开始，每个节点占一个端口
3. **并发安全**：每个端口独立，可以多个程序同时使用不同端口
4. **自动去重**：相同 tag 的节点会自动加后缀区分
5. **停止后释放**：`python3 proxy_pool.py stop` 会杀掉 sing-box 进程，释放所有端口

## 故障排查

| 问题 | 解决 |
|------|------|
| `Connection refused` | 代理池未启动，执行 `python3 proxy_pool.py start` |
| 节点全部超时 | 订阅可能过期，检查订阅链接是否有效 |
| `socksio not installed` | 执行 `uv add socksio` 或 `pip install socksio` |
| sing-box 启动失败 | 检查端口是否被占用：`lsof -i :11000` |
| hysteria2 节点不通 | WSL 对 UDP 支持有限，优先用 vless+gRPC 节点 |
