# 编码规范 — 防止重复犯错

## 1. 数据转换：单一职责，不重复转换

**规则**：每个数据转换只在一个地方做。调用方必须了解函数返回值的单位/格式。

**反例**：
```python
# get_user_info 内部已经做了 quota / 500000
info = get_user_info(...)
balance = info.get('quota', 0) / 500000  # ❌ 重复转换
```

**正例**：
```python
info = get_user_info(...)  # 返回值 quota 已是美元 float
balance = str(info.get('quota', 0))  # ✅ 直接使用
```

**执行方式**：
- 函数 docstring 必须标注返回值的单位/格式
- 涉及单位转换的函数必须有单元测试

---

## 2. 字段映射：声明式，不手写

**规则**：外部数据写入内部模型时，用映射表自动转换，不逐字段手写。

**反例**：
```typescript
// 每加一个字段就要手动加一行，容易遗漏
await repo.put(username, {
  refresh_token: str(item.refreshToken),
  access_token: str(item.accessToken),
  // 忘了 checkin_time...
});
```

**正例**：
```typescript
const FIELD_ALIASES = { refreshToken: "refresh_token", ... };
const fields = toAccountFields(input);  // 自动映射所有字段
await repo.put(username, fields);
```

**执行方式**：
- 新增 Account 字段时，只需更新 `FIELD_ALIASES` 或 `STRING_FIELDS`
- 所有 handler 共用同一个 `toAccountFields()`

---

## 3. 纯函数优先：可测试 > 方便

**规则**：数据转换逻辑必须提取为纯函数（无 IO、无副作用），方便单元测试。

**反例**：
```python
def run():
    # 100 行函数：文件读取 + HTTP + 数据转换 + 重试 + 延时
    ...
    result["balance"] = str(info.get("quota", 0) / 500000)  # 埋在深处，无法单独测试
```

**正例**：
```python
def format_balance(info: dict) -> str:
    """info['quota'] 已是美元 float。"""
    return str(info.get("quota", 0))

def run():
    ...
    result["balance"] = format_balance(info)  # 调用纯函数
```

**执行方式**：
- 任何数据转换逻辑都必须有对应的单元测试
- 测试必须包含回归用例（防止"重复转换"类 bug）

---

## 4. 写入不覆盖：undefined/空值不写入

**规则**：更新记录时，`undefined`/`null`/空字符串不应覆盖已有数据。

**反例**：
```typescript
const merged = { ...existing, ...data };  // ❌ data 中的 undefined 会覆盖
```

**正例**：
```typescript
const clean = Object.fromEntries(
  Object.entries(data).filter(([, v]) => v !== undefined)
);
const merged = { ...existing, ...clean };  // ✅ 只写有值的字段
```

---

## 5. 改动前先写测试

**规则**：修改数据转换/格式化逻辑前，先写（或确认已有）覆盖该路径的测试。改完跑测试验证。

**流程**：
1. 写测试描述期望行为
2. 确认测试通过（当前行为正确）或失败（确认 bug）
3. 改代码
4. 跑测试验证

---

## 6. 手动操作后验证

**规则**：手动回写数据到 KV/DB 后，必须读回验证格式正确。

```bash
# 写入后立即验证
curl -s ... | python3 -c "..."  # 确认字段值符合预期格式
```
