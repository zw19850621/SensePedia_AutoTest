# HKCED 最终答复抽取 — 测试团队接入指南

面向测试自动化工程：告诉你如何从 agent-platform 提取"页面上最终显示给用户的那段话"，不依赖浏览器。

- 代码：`tests/hkced_final_answer_client.py`
- 单测：`tests/test_platform_api/test_hkced_final_answer.py` (30 passed)
- 分支：`hk_customs`，commit `f48cb93`

---

## 1. 先理解：为什么不是单次 JSON 调用

UI 上那个绿色「官方答复 HKCED」信封，可能来自四条路径中的任意一条：

| 路径 | 来源 | 后端信号 | 前端处理 |
|---|---|---|---|
| A. **intent 命中** | HKCED 预过滤器 | SSE `event: intent_email`（body 已含完整信封） | 直接渲染 |
| B. **检索无命中** | rag-query | SSE `event: done, status: "no_answer"`，无 token | **前端合成信封** |
| C. **LLM 说找不到** | LLM 合成 | 正常 SSE token，`done.status = "completed"` | **前端识别关键词后替换成信封** |
| D. **正常 RAG 回答** | LLM 合成 | 正常 SSE token + citations | 原样渲染 |

> 路径 B 和 C 的信封**只存在于前端**。纯 curl 拿到的是"无 token"或"原始 LLM 道歉文本"，不是信封。
>
> 测试要和 UI 100% 对齐，必须在测试侧复刻这个判定逻辑 —— 我们把它做好了，就是本 repo 的 Python 客户端。

---

## 2. 三种接入姿势（按门槛从高到低）

### 姿势一：Python 客户端（推荐，3 行搞定）

适合有 Python 测试框架（pytest / unittest / 私有 harness）。

**依赖**：仅 `httpx`（标准测试栈通常已有）。

```bash
pip install httpx
git clone <agent-platform repo> && cd agent-platform && git checkout hk_customs
```

**用法**：

```python
import os, requests
from tests.hkced_final_answer_client import fetch_final_answer

# 1. 拿 JWT（一次就够，可缓存）
r = requests.post(
    "http://192.168.2.141:8000/v1/auth/login",
    json={"username": "admin", "password": "changeme"},
    timeout=10,
)
token = r.json()["token"]

# 2. 问一个问题，拿到结构化最终答复
result = fetch_final_answer(
    base_url="http://192.168.2.141:8000",
    query="怎么申报HS编码？",
    knowledge_base_id="ALL_KB",
    scope_mode="all",
    headers={"Authorization": f"Bearer {token}"},
)

# 3. 按 answer_type 分支断言
assert result.answer_type in ("intent_email", "no_answer", "rag_answer")
print(result.answer_type)     # 哪条路径
print(result.display_body)    # UI 上那段文字
print(result.plain_text)      # 剥掉信封 chrome 的纯文本
print(result.intent_quote)    # {intent_id, intent_name}（命中时非空）
print(result.citations)       # 引用列表（rag_answer 才有）
```

**返回结构**（dataclass）：

```python
FinalAnswer(
    answer_type: "intent_email" | "no_answer" | "rag_answer" | "error" | "empty",
    display_body: str,           # UI 实际渲染的完整 markdown
    plain_text: str,             # 剥掉信封头尾后的纯文字
    lang: "zh-hk" | "en-us",
    intent_quote: {"intent_id": str, "intent_name": str},
    citations: list[dict],
    retrieval_trace: dict | None,
    raw_events: list[dict],      # 所有 SSE 事件（调试用）
    done_status: str | None,
    error: dict | None,
)
```

---

### 姿势二：纯 curl（适合 smoke / CI shell）

**Step 1 — 登录拿 token**：

```bash
TOKEN=$(curl -s -X POST http://192.168.2.141:8000/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"changeme"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
```

**Step 2 — 发起流式查询**：

```bash
curl -N -X POST 'http://192.168.2.141:8000/v1/rag/query/stream' \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "怎么申报HS编码？",
    "knowledge_base_id": "ALL_KB",
    "scope_mode": "all",
    "model": "qwen3.5-plus",
    "lang": "zh-hk"
  }'
```

> `-N` 关闭 curl buffer，SSE 事件实时出来。

**输出样例（路径 A — intent 命中）**：

```
event: intent_email
data: {"body":"敬啟者：\n\n根據查詢結果……\n\n香港海關","lang":"zh-hk","intent_quote":{"intent_id":"I42","intent_name":"HS编码咨询"}}

event: done
data: {"status":"ok"}
```

**输出样例（路径 B — 检索空）**：

```
event: retrieval
data: {"retrieved_count":0,"trace":{"merged":[]}}

event: done
data: {"status":"no_answer"}
```

**输出样例（路径 D — 正常 RAG）**：

```
event: retrieval
data: {"retrieved_count":5,"trace":{...}}

event: token
data: {"delta":"HS 编码申报流程包括"}

event: token
data: {"delta":"三个步骤[ref_1]。"}

event: done
data: {"status":"completed","citations":[{"ref_id":"ref_1","doc_id":"doc-a"}]}
```

**shell 解析最小示例**（只做 smoke）：

```bash
curl -N -X POST ... \
  | awk '
      /^event: intent_email/ { getline line; sub(/^data: /, "", line); print "HIT:", line; exit }
      /^event: done/         { getline line; sub(/^data: /, "", line); print "END:", line; exit }
    '
```

---

### 姿势三：HTTP 后处理自己做（不推荐，易漂）

如果测试工程不是 Python，自己实现：

1. POST `/v1/rag/query/stream`，按 `\n\n` 切分 SSE
2. 每块里找 `event:` 和 `data:`，`data` 是 JSON
3. 按下面规则归并（必须按此优先级）：

```
如果见到 intent_email 事件     → 答复 = event.body，type = intent_email
否则 done.status == "no_answer" 且无 token → 答复 = 信封模板（见 §3），type = no_answer
否则聚合 token，匹配 NO_ANSWER 正则（见 §3） → 答复 = 信封模板，type = no_answer
否则聚合 token                → 答复 = 聚合文本，type = rag_answer
```

> **强烈建议跟我们 Python 客户端对齐** —— 那 15 个正则后续若调整，必须同步更新。

---

## 3. 需要镜像的前端逻辑（供参考）

### no-answer 识别关键词（`NO_ANSWER_PATTERNS_ZH`）

任一 substring 命中即视为 no-answer：

```
"未能找到相關資料", "未能找到相关资料",
"沒有找到相關",   "没有找到相关",
"沒有相關資料",   "没有相关资料",
"提供的參考資料中沒有", "提供的参考资料中没有",
"參考資料中沒有關於",   "参考资料中没有关于",
"無法回答",       "无法回答",
"沒有相關信息",   "没有相关信息",
"找不到相關",     "找不到相关"
```

来源：`services/frontend-web/src/views/chat/KnowledgeChat.vue:148-162`。前后端必须一致。

### 信封模板（触发后合成）

**中文**：
```
敬啟者：

抱歉，未能找到相關資料

香港海關
```

**英文**：
```
Dear Sir/Madam,

Sorry, no relevant information was found.

Hong Kong Customs
```

---

## 4. 历史会话抽取（另一个入口）

如果你只想读某个会话的全部历史消息（离线做批量断言）：

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://192.168.2.141:8000/v1/rag/sessions/<SESSION_ID>
```

返回 `{session, messages: [...]}`，`messages[i].content` 可能以 `<!--hkced-meta:{...}-->` 开头 —— 这是被持久化的 intent 元数据，**剥掉首行即为信封正文**。

Python 客户端里一个函数搞定：

```python
from tests.hkced_final_answer_client import detect_envelope_from_content

envelope = detect_envelope_from_content(message["content"])
if envelope:
    print(envelope["body"])           # 信封正文
    print(envelope["intent_quote"])   # {intent_id, intent_name}
else:
    print(message["content"])         # 普通 LLM 回复
```

---

## 5. 常见坑（测试团队踩过的）

| 坑 | 症状 | 解决 |
|---|---|---|
| 用 `requests.post(...).json()` | 报 `JSONDecodeError` | 这是 SSE 不是 JSON，用 httpx.stream 或 sseclient |
| 没带 `Authorization` | HTTP 401 | 先 `/v1/auth/login` 拿 token |
| 用 `knowledge_base_id: "default"` | 查不到东西 | 虚拟全库用 `ALL_KB`（大写），不是 `default` |
| curl 没加 `-N` | SSE 卡住不输出 | 加 `-N` 禁用 buffer |
| 首 token 超过 2 分钟没出来 | 以为超时 | 后端 LLM 冷启动正常现象，SSE 整体不限时，只要连接活着等即可 |
| LLM 回 "未能找到相关资料" 但 `done.status=completed` | 以为是正常回答 | 正是路径 C，必须在测试侧做 no-answer 判定 |

---

## 6. 基础参数速查

| 参数 | 必填 | 建议值 | 说明 |
|---|---|---|---|
| `query` | ✅ | 用户问题原文 | 单轮 |
| `session_id` | 否 | UUID 字符串 | 带上则后端自动加载 20 条历史做多轮 |
| `knowledge_base_id` | 否 | `ALL_KB` | 全库；具体 KB 传真 ID |
| `scope_mode` | 否 | `all` | `all` / `kb` / `docs` |
| `doc_ids` | 否 | `[]` | 指定文档 ID 列表，优先级高于 kb_id |
| `model` | 否 | `qwen3.5-plus` | 也可传 `qwen3.5-27b-local` 等 |
| `lang` | 否 | `zh-hk` | 影响信封语言 |
| `top_k` | 否 | 30 | 检索召回数 |
| `rerank` | 否 | true | 是否 rerank |

默认环境变量：7023 是 `192.168.2.141:8000`（内网）。实际以运维通知为准。

---

## 7. 快速自测

```bash
# 前置：本 repo 已 clone，切到 hk_customs 分支
git checkout hk_customs
pip install -e services/platform-api  # 或按仓库 README 走
cd <agent-platform>

# 跑单测证明客户端能工作
pytest tests/test_platform_api/test_hkced_final_answer.py -v
# 期望：30 passed in 0.03s
```

---

## 8. 有问题找谁

- **客户端 bug / 补路径**：agent-platform 维护团队（此分支）
- **后端接口变更**：RAG / HKCED 组（`docs/design/hk-customs-intent-integration/`）
- **7023 环境问题**：OPS（`docs/e2e-testing-deployment-guide.md`）

> 若前端 `NO_ANSWER_PATTERNS_ZH` 调整，请同步更新 `tests/hkced_final_answer_client.py` 顶部常量，避免飘移。
