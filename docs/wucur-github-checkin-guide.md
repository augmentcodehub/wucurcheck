# Wucur GitHub 自动签到教程

本文档只针对 `http://wucur.com:6543` 这个站点，说明如何在 GitHub Actions 中实现：

- 每天自动登录
- 每天自动签到
- 获取余额与已使用额度
- 通过 `Server酱` 接收通知

## 适用前提

当前仓库已经内置 `wucur` provider，不需要你再额外配置 `PROVIDERS`。

`wucur` 的实际认证链路已经验证通过：

1. `POST /api/user/login`
2. 服务端返回 `session` cookie
3. 使用该 `session` 调用 `/api/user/checkin`
4. 使用 `/api/user/self` 获取余额信息

## 你需要准备的信息

你至少需要准备两项：

1. `wucur` 账号邮箱
2. `wucur` 账号密码

如果你还需要通知，则再准备：

1. `Server酱` 的 `SendKey`

## GitHub 配置位置

进入你 fork 后的仓库：

1. 打开 `Settings`
2. 进入 `Environments`
3. 新建或打开 `production`
4. 在 `production` 下添加 `Environment secrets`

## 必填 Secrets

### 1. `ANYROUTER_ACCOUNTS`

单账号示例：

```json
[
  {
    "name": "主账号",
    "provider": "wucur",
    "username": "your_email@example.com",
    "password": "your_password"
  }
]
```

字段说明：

- `name`：账号名称，显示在日志和通知里
- `provider`：固定写 `wucur`
- `username`：登录邮箱
- `password`：登录密码

### 2. `SERVERPUSHKEY`

```text
你的Server酱SendKey
```

如果你不需要通知，可以先不配这个值，但建议配置，方便你知道签到失败或余额变化。

## 多账号配置

这个项目支持 `n` 个账号签到，直接把多个账号放到 `ANYROUTER_ACCOUNTS` 数组里即可。

双账号示例：

```json
[
  {
    "name": "主账号",
    "provider": "wucur",
    "username": "user1@example.com",
    "password": "pass1"
  },
  {
    "name": "备用账号",
    "provider": "wucur",
    "username": "user2@example.com",
    "password": "pass2"
  },
  {
    "name": "测试账号",
    "provider": "wucur",
    "username": "user3@example.com",
    "password": "pass3"
  }
]
```

10 账号可复制模板：

```json
[
  {
    "name": "账号1",
    "provider": "wucur",
    "username": "user1@example.com",
    "password": "your_password_1"
  },
  {
    "name": "账号2",
    "provider": "wucur",
    "username": "user2@example.com",
    "password": "your_password_2"
  },
  {
    "name": "账号3",
    "provider": "wucur",
    "username": "user3@example.com",
    "password": "your_password_3"
  },
  {
    "name": "账号4",
    "provider": "wucur",
    "username": "user4@example.com",
    "password": "your_password_4"
  },
  {
    "name": "账号5",
    "provider": "wucur",
    "username": "user5@example.com",
    "password": "your_password_5"
  },
  {
    "name": "账号6",
    "provider": "wucur",
    "username": "user6@example.com",
    "password": "your_password_6"
  },
  {
    "name": "账号7",
    "provider": "wucur",
    "username": "user7@example.com",
    "password": "your_password_7"
  },
  {
    "name": "账号8",
    "provider": "wucur",
    "username": "user8@example.com",
    "password": "your_password_8"
  },
  {
    "name": "账号9",
    "provider": "wucur",
    "username": "user9@example.com",
    "password": "your_password_9"
  },
  {
    "name": "账号10",
    "provider": "wucur",
    "username": "user10@example.com",
    "password": "your_password_10"
  }
]
```

如果你是在 GitHub Secret 里粘贴，推荐直接使用单行 JSON，能减少换行和逗号错误：

```json
[{"name":"账号1","provider":"wucur","username":"user1@example.com","password":"your_password_1"},{"name":"账号2","provider":"wucur","username":"user2@example.com","password":"your_password_2"},{"name":"账号3","provider":"wucur","username":"user3@example.com","password":"your_password_3"},{"name":"账号4","provider":"wucur","username":"user4@example.com","password":"your_password_4"},{"name":"账号5","provider":"wucur","username":"user5@example.com","password":"your_password_5"},{"name":"账号6","provider":"wucur","username":"user6@example.com","password":"your_password_6"},{"name":"账号7","provider":"wucur","username":"user7@example.com","password":"your_password_7"},{"name":"账号8","provider":"wucur","username":"user8@example.com","password":"your_password_8"},{"name":"账号9","provider":"wucur","username":"user9@example.com","password":"your_password_9"},{"name":"账号10","provider":"wucur","username":"user10@example.com","password":"your_password_10"}]
```

脚本会按顺序逐个执行：

1. 登录
2. 获取余额
3. 执行签到
4. 汇总结果
5. 发送通知

## 不需要配置的项

对于 `wucur`，你通常不需要再配置这些内容：

- `PROVIDERS`
- `cookies`
- `api_user`

原因是当前仓库已经内置了 `wucur` 的正确逻辑：

- 自动用 `username/password` 登录
- 自动建立 `session` cookie
- 自动从登录结果里提取用户 `id`
- 自动查询 `/api/user/self`
- 自动执行 `/api/user/checkin`

## 工作流触发方式

当前工作流支持两种触发方式：

1. 手动触发
2. 定时触发

默认定时是每 6 小时运行一次。这样做的好处是：

- 即使某次 GitHub 调度延迟，也还有后续补跑机会
- 即使站点临时异常，也有再次执行的机会

## 首次验证方法

建议配置完 Secrets 后，先手动触发一次：

1. 打开仓库的 `Actions`
2. 进入 `AnyRouter 自动签到`
3. 点击 `Run workflow`
4. 等待执行完成

你应该在日志中看到类似信息：

1. 使用 `wucur` provider
2. `Session login successful`
3. 当前余额和已使用额度
4. `Check-in successful` 或 `Already checked in today`

## 余额获取说明

当前 `wucur` 已验证可以获取余额信息。

脚本会调用：

- `/api/user/self`

然后解析出：

- 当前余额
- 已使用额度

这些信息会在日志里显示，也会参与通知内容生成。

## 通知触发规则

当前逻辑下，通常会在这些场景发送通知：

1. 某个账号签到失败
2. 首次运行
3. 余额发生变化

如果全部账号都成功，并且余额没有变化，则可能跳过通知。

## 常见问题

### 1. 需要配置 `PROVIDERS` 吗

不需要。

`wucur` 已经是内置 provider。

### 2. 需要先手动获取 cookie 吗

不需要。

当前实现会自动登录并获取服务端设置的 `session` cookie。

### 3. 需要提供 `api_user` 吗

不需要手动提供。

脚本会在登录后自动处理该站点需要的用户信息查询头。

### 4. 支持多个账号吗

支持。

把多个账号放进 `ANYROUTER_ACCOUNTS` 数组即可。

### 5. 可以看到余额吗

可以。

当前站点已验证能成功读取余额和已使用额度。

## 推荐最终配置

最常见的生产配置只需要两个 Secret：

`ANYROUTER_ACCOUNTS`

```json
[
  {
    "name": "主账号",
    "provider": "wucur",
    "username": "your_email@example.com",
    "password": "your_password"
  }
]
```

`SERVERPUSHKEY`

```text
你的Server酱SendKey
```

## 结论

对于 `wucur`，当前仓库已经具备完整能力：

- 支持自动登录
- 支持自动签到
- 支持多账号
- 支持余额获取
- 支持 `Server酱` 通知

你只需要在 GitHub `production` 环境里配置好 Secret，就可以直接使用。

## 附：注册脚本

如果你想先看每个命令的作用，统一入口是：

```bash
uv run wucur help
```

查看某个命令的说明：

```bash
uv run wucur help export
```

如果你更喜欢旧路径，也可以继续用：

```bash
uv run scripts/wucur.py help
```

如果你还需要批量或半批量注册账号，统一入口也可以直接调用：

```bash
uv run wucur register --file one-account.json --skip-checkin
```

旧的 `scripts/*.py` 入口仍然保留，主要用于兼容现有流程。

如果你更习惯按单个脚本执行，仓库里也保留了这些独立脚本：

- [scripts/register_wucur.py](../scripts/register_wucur.py)
- [scripts/register_one_account.py](../scripts/register_one_account.py)

它的默认流程是：

1. 注册账号
2. 登录账号
3. 获取余额
4. 执行签到

另外，脚本现在会在注册和登录成功后自动把账号追加到本地 `accounts.json`。

这个文件的内容就是 `ANYROUTER_ACCOUNTS` 可直接使用的 JSON 数组格式。

### 基本用法

```bash
python scripts/register_wucur.py --username your_email@example.com --password your_password
```

如果你希望写入自定义显示名称：

```bash
python scripts/register_wucur.py --name "账号1" --username your_email@example.com --password your_password
```

### 只注册并登录，不执行签到

```bash
python scripts/register_wucur.py --username your_email@example.com --password your_password --skip-checkin
```

### 输出 JSON 结果

```bash
python scripts/register_wucur.py --username your_email@example.com --password your_password --json
```

### 本地输出文件

默认输出文件：

```text
accounts.json
```

默认写入格式示例：

```json
[
  {
    "name": "账号1",
    "provider": "wucur",
    "username": "user1@example.com",
    "password": "your_password_1"
  },
  {
    "name": "账号2",
    "provider": "wucur",
    "username": "user2@example.com",
    "password": "your_password_2"
  }
]
```

这个文件可以直接复制为 GitHub Secret：

- `Name`: `ANYROUTER_ACCOUNTS`
- `Value`: `accounts.json` 的完整内容

### 当前脚本前提

当前站点已经验证为：

- 不需要邮箱验证码
- 不需要 Turnstile

如果后续站点开启验证码或邮箱校验，这个脚本就需要再调整。

### 单组账号 JSON 执行器

如果你已经有一组账号 JSON，希望直接执行单账号注册，推荐优先使用文件方式：

```bash
uv run scripts/register_one_account.py --file one-account.json --skip-checkin
```

也支持标准输入：

```bash
cat one-account.json | uv run scripts/register_one_account.py --stdin --skip-checkin
```

它会明确打印：

- 输入校验是否通过
- 是否开始调用底层注册脚本
- 注册流程成功或失败

### 注册成功后写入 SQLite

如果你希望注册成功后，把这些信息写入本地 `SQLite`：

- 注册账号
- 密码
- 注册时间
- 签到前余额
- 签到后余额
- 余额变化

可以使用：

```bash
uv run scripts/register_one_account_to_db.py --file one-account-checkin-next.json
```

默认数据库文件：

```text
wucur_accounts.sqlite3
```

### 查询 SQLite 里的注册记录

如果你要查看最近注册的账号、密码、注册时间和余额：

```bash
uv run scripts/query_wucur_accounts_db.py
```

默认显示最近 `20` 条。

如果你要指定条数：

```bash
uv run scripts/query_wucur_accounts_db.py --limit 50
```

### 导出两种格式

如果你要把 SQLite 里的账号导出成：

1. GitHub Secrets 可直接粘贴的 JSON
2. CSV 备份

可以使用：

```bash
uv run scripts/export_wucur_accounts.py
```

默认会生成：

```text
github-secrets-accounts.json
accounts.csv
```

如果你还想把 GitHub Secrets 的 JSON 同时打印到终端：

```bash
uv run scripts/export_wucur_accounts.py --stdout-json
```

### 一条命令跑完整本地流程

如果你希望一条命令完成：

1. 生成安全测试账号
2. 注册并签到
3. 写入 SQLite
4. 导出 GitHub Secrets JSON
5. 导出 CSV

可以使用：

```bash
uv run scripts/run_wucur_pipeline.py --sequence 15
```

## 附：规则生成器与注册包装器

如果你希望把“账号规则生成”和“实际注册”解耦，仓库里现在分成两层：

- [scripts/account_rule_engine.py](../scripts/account_rule_engine.py)
- [scripts/generate_accounts.py](../scripts/generate_accounts.py)
- [scripts/register_wucur_wrapper.py](../scripts/register_wucur_wrapper.py)

用途分别是：

1. `account_rule_engine.py`
   纯规则引擎，负责按配置生成账号数据
2. `generate_accounts.py`
   只生成账号，不调用注册
3. `register_wucur_wrapper.py`
   生成 1 个账号后，调用底层 [scripts/register_wucur.py](../scripts/register_wucur.py)

### 第一步：生成配置文件

```bash
python scripts/generate_accounts.py --init-config
```

执行后会生成：

```text
register_wucur_wrapper.json
```

### 第二步：编辑配置文件

示例：

```json
{
  "name_prefix": "账号",
  "email_prefix": "user",
  "email_domain": "example.com",
  "password": "123Claude&Codex",
  "timestamp_format": "%m%d%H%M%S",
  "random_length": 0,
  "separator": "",
  "seed_template": "{time}{rand}",
  "name_template": "{name_prefix}{seed}",
  "email_local_template": "{email_prefix}{separator}{seed}",
  "name_regex": "",
  "name_replacement": "",
  "email_local_regex": "",
  "email_local_replacement": "",
  "skip_checkin": true,
  "json_output": false
}
```

字段说明：

- `name_prefix`：账号名称前缀
- `email_prefix`：邮箱名前缀
- `email_domain`：邮箱域名
- `password`：注册密码
- `timestamp_format`：时间后缀格式
- `random_length`：随机字符长度
- `separator`：前缀与后缀之间的连接符
- `seed_template`：种子模板，可使用 `{time}` `{rand}`
- `name_template`：名称模板，可使用 `{name_prefix}` `{seed}`
- `email_local_template`：邮箱本地部分模板，可使用 `{email_prefix}` `{separator}` `{seed}`
- `name_regex`：对生成后的 `name` 再做正则处理
- `name_replacement`：`name_regex` 的替换模板
- `email_local_regex`：对生成后的邮箱本地部分再做正则处理
- `email_local_replacement`：`email_local_regex` 的替换模板
- `skip_checkin`：是否跳过签到
- `json_output`：是否输出 JSON 结果

### 第三步：只生成账号，不注册

```bash
python scripts/generate_accounts.py --stdout
```

它会按规则生成多组账号，并输出到：

- `generated_accounts.json`

如果配置里 `count` 是 `10`，就会生成 10 组。

### 第四步：生成 1 组并调用注册脚本

```bash
python scripts/register_wucur_wrapper.py
```

它会自动生成类似：

- `name`: `账号0514130105`
- `username`: `user0514130105@example.com`

然后继续调用底层注册脚本，并自动把成功账号追加到 `accounts.json`。

### 自定义配置文件路径

```bash
python scripts/generate_accounts.py --config my-register-rule.json --stdout
```

或：

```bash
python scripts/register_wucur_wrapper.py --config my-register-rule.json
```

### 正则规则示例

如果你希望用正则进一步改写生成结果，可以这样配置：

```json
{
  "name_prefix": "账号",
  "email_prefix": "user",
  "email_domain": "example.com",
  "password": "123Claude&Codex",
  "timestamp_format": "%m%d%H%M%S",
  "random_length": 2,
  "separator": "",
  "seed_template": "{time}{rand}",
  "name_template": "{name_prefix}{seed}",
  "email_local_template": "{email_prefix}{seed}",
  "name_regex": "^账号(\\d{4})(\\d+)$",
  "name_replacement": "账号-$1-$2",
  "email_local_regex": "^user",
  "email_local_replacement": "wc",
  "skip_checkin": true,
  "json_output": false
}
```

这会把类似：

- `账号0514131500ab`
- `user0514131500ab@example.com`

进一步改写成：

- `账号-0514-131500ab`
- `wc0514131500ab@example.com`
