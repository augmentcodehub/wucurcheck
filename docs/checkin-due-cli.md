# checkin-due CLI

`checkin-due` 是本地的薄入口，只负责三件事：

1. 解析参数
2. 构造仓库
3. 调用 `CheckinDueService`

它不包含签到规则本身，规则仍然留在 `scripts/checkin_due_service.py` 和 `scripts/checkin_due_domain.py`。

如果你刚拉完代码后提示 `program not found`，先执行一次 `uv sync`，让新的 console script 安装到环境里。

## 用法

```bash
uv run checkin-due --help
```

常见命令：

```bash
uv run checkin-due --backend sqlite --db wucur_accounts.sqlite3 --dry-run
```

```bash
uv run checkin-due --backend sqlite --db wucur_accounts.sqlite3
```

如果你使用远端仓库后端：

```bash
uv run checkin-due --backend worker --worker-url https://worker.example.com --worker-token xxx
```

## 参数

- `--backend`：`sqlite` 或 `worker`
- `--db`：SQLite 数据库路径
- `--worker-url`：worker 后端地址
- `--worker-token`：worker 后端 token
- `--as-of`：手动指定判断日期
- `--timezone`：未指定 `--as-of` 时使用的时区
- `--dry-run`：只分类，不写回结果
- `--provider-scope`：默认 `wucur`

## 输出

命令结束时会打印一个简要汇总，例如：

```text
[SUMMARY] scanned=10 due=3 skipped=7 succeeded=3 failed=0
```

如果发生错误，进程退出码会反映 `CheckinDueService` 的结果。
