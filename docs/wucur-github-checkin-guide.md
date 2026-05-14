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
