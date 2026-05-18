# 本地命令使用指南

## 前置条件

```bash
cd /home/administrator/workspace/open-source/wucurcheck
uv sync  # 首次安装依赖
```

## 一、注册

### 方式 1：Pipeline（推荐，一条命令完成生成+注册+写库+导出）

```bash
# 注册 1 个账号（sequence 是序号，每次不同即可）
uv run wucur pipeline --sequence 1

# 指定域名和密码
uv run wucur pipeline --sequence 2 --domain qq.com --password "123Claude&Codex"

# 连续注册多个（每次换序号）
for i in $(seq 1 10); do uv run wucur pipeline --sequence $i; sleep 10; done
```

### 方式 2：用代理池批量注册（绕过 IP 限流）

```bash
# 先启动代理池
cd /home/administrator && python3 proxy_pool.py start

# 批量注册（自动轮换 IP）
cd /home/administrator/workspace/open-source/wucurcheck
uv run python -c "
import json, random, httpx, time, sys
sys.path.insert(0, 'python/src')
from adapters.http.wucur_client import register_account

proxies = json.load(open('/home/administrator/proxy-pool-list.json'))
available = [p['proxy'] for p in proxies[:4]]

fruits = ['fig','plum','lime','pear','kiwi','date','grape','berry']
animals = ['fox','cat','owl','ant','bat','dog','eel','elk','emu','fly','gnu','hen','jay','ox','yak']

for i in range(10):
    w1, w2, n = random.choice(fruits), random.choice(animals), random.randint(0,9)
    username = f'{w1}{n}{w2}@qq.com'
    proxy = available[i % len(available)]
    client = httpx.Client(http2=True, timeout=30, proxy=proxy)
    r = register_account(client, username, '123Claude&Codex')
    print(f'{username}: {\"✅\" if r.get(\"success\") else \"❌ \"+r.get(\"message\",\"\")}')
    client.close()
    time.sleep(3)
"
```

### 方式 3：单个账号注册

```bash
# 直接指定账号信息
uv run wucur register --json-input '{"name":"test","provider":"wucur","username":"fig3cat@qq.com","password":"123Claude&Codex"}'
```

## 二、查询

```bash
# 查询最近 20 条（默认）
uv run wucur query

# 查询全部
uv run wucur query --limit 99999

# 指定数据库文件
uv run wucur query --db artifacts/wucur_accounts.sqlite3 --limit 50
```

## 三、签到

### 方式 1：签到全部账号（从环境变量读取）

```bash
# 需要设置 ANYROUTER_ACCOUNTS 环境变量
export ANYROUTER_ACCOUNTS='[{"name":"wucur","provider":"wucur","username":"fig3cat@qq.com","password":"123Claude&Codex"}]'
uv run checkin.py
```

### 方式 2：批量签到指定账号（checkin_batch.py）

```bash
# 准备账号列表
cat > artifacts/checkin_accounts.json << 'EOF'
[
  {"username": "fig3cat@qq.com", "password": "123Claude&Codex"},
  {"username": "plum8fox@qq.com", "password": "123Claude&Codex"}
]
EOF

# 执行签到（间隔 5-10 秒）
uv run python python/src/scripts/checkin_batch.py
```

### 方式 3：从导出文件生成签到列表

```bash
# 先导出账号
uv run wucur export --db artifacts/wucur_accounts.sqlite3

# 用导出的 JSON 签到
cat artifacts/github_secrets_accounts.json | python3 -c "
import json, sys
accounts = json.load(sys.stdin)
checkin_list = [{'username': a['username'], 'password': a['password']} for a in accounts]
json.dump(checkin_list, open('artifacts/checkin_accounts.json', 'w'), indent=2)
print(f'生成 {len(checkin_list)} 个账号的签到列表')
"
uv run python python/src/scripts/checkin_batch.py
```

## 四、导出

```bash
# 导出为 JSON + CSV
uv run wucur export

# 指定输出路径
uv run wucur export --db artifacts/wucur_accounts.sqlite3 --json-output artifacts/accounts.json --csv-output artifacts/accounts.csv
```

## 五、其他命令

```bash
# 生成账号（不注册）
uv run wucur generate --config artifacts/register_wucur_wrapper.json --stdout

# 生成自然用户名
uv run python python/src/tools/account_generation/gen_natural_accounts.py 10 qq.com "123Claude&Codex" "fruit+animal"

# 查看帮助
uv run wucur help
uv run wucur help pipeline
```

## 注意事项

- 用户名总长度（含@域名）不能超过 15 字符，推荐用 `qq.com`
- 注册有 IP 限流，同 IP 间隔至少 30 秒，用代理池可降到 3 秒
- 签到无明显限流，5-10 秒间隔即可
- 数据库默认路径：`artifacts/wucur_accounts.sqlite3`
