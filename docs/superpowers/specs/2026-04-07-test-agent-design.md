# SensePedia 自动化测试 Agent 设计文档

**版本**: 1.0  
**日期**: 2026-04-07  
**状态**: 草案  
**作者**: AutoTest Team

---

## 目录

1. [概述](#1-概述)
2. [当前框架分析](#2-当前框架分析)
3. [目标与范围](#3-目标与范围)
4. [总体架构](#4-总体架构)
5. [核心模块设计](#5-核心模块设计)
6. [数据流设计](#6-数据流设计)
7. [配置设计](#7-配置设计)
8. [CLI 接口设计](#8-cli 接口设计)
9. [实现计划](#9-实现计划)
10. [风险与依赖](#10-风险与依赖)

---

## 1. 概述

### 1.1 背景

SensePedia 项目需要一个智能化的自动化测试系统，能够：
- 根据指令自动生成测试用例
- 执行测试并进行多维度断言
- 输出详细的测试结果和报告

### 1.2 目标

构建一个本地命令行驱动的测试 Agent，实现：
1. **测试用例自动生成** - 从文档/API/知识库自动生成测试用例
2. **智能断言** - 支持功能断言和精度断言
3. **测试执行** - 执行问答测试和接口测试
4. **报告生成** - 生成 Markdown/HTML/控制台报告

### 1.3 使用场景

```bash
# 场景 1: 从需求文档生成测试用例
python main.py --generate --source "docs/requirements.pdf" --output "tests/cases.yaml"

# 场景 2: 执行测试并断言
python main.py --execute --testset "tests/cases.yaml" --assertions "tests/assertions.yaml"

# 场景 3: 查看测试报告
python main.py --report --results "tests/results.json" --format html
```

---

## 2. 当前框架分析

### 2.1 现有架构

```
SensePedia_AutoTest/
├── main.py                      # CLI 入口
├── test_framework.py            # 测试框架
├── src/
│   ├── agents/
│   │   └── test_agent.py        # AutoTest Agent (已有)
│   ├── core/
│   │   ├── config.py            # 配置加载 (已有)
│   │   ├── auth.py              # 认证管理 (已有)
│   │   └── client.py            # HTTP 客户端 (已有)
│   ├── drivers/
│   │   ├── document_driver.py   # 文档上传 (已有)
│   │   └── qa_driver.py         # 问答测试 (已有)
│   └── reporters/
│       └── report_generator.py  # 报告生成 (已有)
└── config/
    ├── endpoints.yaml           # API 端点配置
    ├── scenarios.yaml           # 测试场景配置
    └── auth.yaml                # 认证配置
```

### 2.2 现有能力

| 能力 | 状态 | 说明 |
|------|------|------|
| 自然语言命令解析 | ✅ 已有 | 支持"帮我测试 XX 知识库" |
| 文档批量上传 | ✅ 已有 | 支持 PDF/Word/MD/TXT |
| 问答批量测试 | ✅ 已有 | 支持 Excel 测试集 |
| Markdown 报告 | ✅ 已有 | 包含统计和详情 |
| 响应时间统计 | ✅ 已有 | P95/P99 |

### 2.3 缺失能力

| 能力 | 状态 | 优先级 |
|------|------|--------|
| 测试用例自动生成 | ❌ 缺失 | P0 |
| 智能断言引擎 | ❌ 缺失 | P0 |
| HTML 报告 | ❌ 缺失 | P1 |
| 控制台摘要报告 | ❌ 缺失 | P1 |
| 语义相似度对比 | ❌ 缺失 | P1 |

---

## 3. 目标与范围

### 3.1 功能目标

| 功能 | 描述 | 优先级 |
|------|------|--------|
| 测试用例生成 | 从文档/API/知识库生成测试用例 | P0 |
| 功能断言 | 关键词匹配、响应时间 | P0 |
| 精度断言 | 语义相似度、知识溯源 | P0 |
| 测试执行 | 问答测试、接口测试 | P0 |
| 报告生成 | Markdown/HTML/控制台 | P0 |

### 3.2 非功能目标

| 目标 | 指标 |
|------|------|
| 易用性 | 单命令完成所有操作 |
| 可扩展 | 支持新增断言类型 |
| 可维护 | 模块职责清晰 |
| 性能 | 支持并发执行 (可配置) |

### 3.3 范围界定

**本期范围（V1.0）**：
- 本地命令行使用
- YAML/Excel 测试用例格式
- 5 种断言类型
- 3 种报告格式

**暂不纳入（V2.0+）**：
- CI/CD 集成（JUnit XML）
- API 服务化
- UI 界面
- 分布式执行

---

## 4. 总体架构

### 4.1 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI 入口层                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  main.py + CLI 参数解析 (--generate/--execute/--report)  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AutoTest Agent                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  意图解析 | 场景匹配 | 任务分发                            │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  TestCase       │ │ Assertion       │ │ Report          │
│  Generator      │ │ Engine          │ │ Generator       │
│  ─────────────  │ │ ──────────────  │ │ ─────────────   │
│  • 文档解析     │ │ • 功能断言       │ │ • Markdown      │
│  • API 解析      │ │ • 精度断言       │ │ • HTML          │
│  • 知识库提取   │ │ • 性能断言       │ │ • 控制台        │
│  • LLM 生成      │ │ • 语义相似度     │ │ • JSON 导出     │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        执行层                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ DocumentDriver  │  │ QADriver        │  │ HttpClient      │  │
│  │ (文档上传)       │  │ (问答测试)       │  │ (API 调用)        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        配置层                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ endpoints.yaml  │  │ scenarios.yaml  │  │ assertions.yaml │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 模块职责

| 模块 | 职责 | 依赖 |
|------|------|------|
| CLI 入口 | 解析命令行参数，调用 Agent | argparse |
| AutoTest Agent | 意图解析、任务分发 | 所有下层模块 |
| TestCaseGenerator | 生成测试用例 | LLM、文档解析器 |
| AssertionEngine | 执行断言 | 语义相似度模块 |
| ReportGenerator | 生成报告 | Jinja2(HTML) |
| DocumentDriver | 文档上传 | HttpClient |
| QADriver | 问答测试 | HttpClient |
| HttpClient | HTTP 请求 | httpx |

---

## 5. 核心模块设计

### 5.1 TestCaseGenerator（测试用例生成器）

#### 5.1.1 职责

从多种数据源自动生成测试用例：
1. 需求文档（PDF/Word/Markdown）
2. API 规范（OpenAPI/Swagger）
3. 知识库内容（通过 API 提取）

#### 5.1.2 接口设计

```python
class TestCaseGenerator:
    def __init__(self, llm_client: LLMClient, config: Config)
    
    # 从文档生成测试用例
    async def generate_from_document(
        source_path: str,
        output_path: str,
        count: int = 50
    ) -> List[TestCase]
    
    # 从知识库生成测试用例
    async def generate_from_knowledge(
        knowledge_base_id: str,
        output_path: str,
        count: int = 50
    ) -> List[TestCase]
    
    # 从 API 规范生成测试用例
    async def generate_from_api(
        openapi_path: str,
        output_path: str
    ) -> List[TestCase]
```

#### 5.1.3 测试用例格式

```python
@dataclass
class TestCase:
    id: str                    # TC001, TC002, ...
    type: str                  # "qa" | "api"
    question: str              # 问答题目
    expected_answer: str       # 预期答案（可选）
    endpoint: str              # API 端点（api 类型）
    method: str                # HTTP 方法
    request_body: dict         # 请求体
    assertions: List[AssertionRule]
    metadata: dict             # 来源文档、生成时间等
```

#### 5.1.4 LLM Prompt 模板

```yaml
# prompts/generate_test_cases.yaml
system_prompt: |
  你是一个专业的测试工程师。请根据提供的文档内容，生成测试用例。
  
  要求：
  1. 每个测试用例包含：问题、预期答案、断言规则
  2. 问题应覆盖文档中的关键信息点
  3. 预期答案应准确反映文档内容
  
  输出格式：YAML

user_prompt: |
  文档内容：
  {document_content}
  
  请生成 {count} 个测试用例。
```

---

### 5.2 AssertionEngine（断言引擎）

#### 5.2.1 职责

执行多维度断言：
1. 功能断言 - 关键词匹配
2. 精度断言 - 语义相似度、知识溯源
3. 性能断言 - 响应时间

#### 5.2.2 接口设计

```python
class AssertionEngine:
    def __init__(self, config: Config, llm_client: LLMClient)
    
    # 执行所有断言
    async def execute_all(
        result: QAResult,
        rules: List[AssertionRule]
    ) -> List[AssertionResult]
    
    # 执行单个断言
    async def execute(
        result: QAResult,
        rule: AssertionRule
    ) -> AssertionResult
```

#### 5.2.3 断言类型

```python
class AssertionType(str, Enum):
    CONTAINS = "contains"              # 包含关键词
    NOT_CONTAINS = "not_contains"      # 不包含
    RESPONSE_TIME = "response_time"    # 响应时间
    SEMANTIC_SIMILARITY = "semantic_similarity"  # 语义相似度
    KNOWLEDGE_GROUNDING = "knowledge_grounding"  # 知识溯源
```

#### 5.2.4 断言规则配置

```yaml
# assertions.yaml
assertions:
  # 全局默认断言
  global:
    - name: "无错误信息"
      type: not_contains
      keywords: ["错误", "失败", "异常", "error", "failed"]
    
    - name: "响应时间达标"
      type: response_time
      threshold: 5.0

  # 测试用例级别断言
  test_cases:
    TC001:
      - name: "包含办公时间"
        type: contains
        keywords: ["9:00", "17:00"]
      
      - name: "与参考答案语义一致"
        type: semantic_similarity
        threshold: 0.85
        reference: "香港海关办公时间为周一至周五 9:00-17:00"
```

#### 5.2.5 断言结果

```python
@dataclass
class AssertionResult:
    rule_name: str
    assertion_type: str
    passed: bool
    message: str             # 人类可读的说明
    details: dict            # 详细数据
    
    # 示例：
    # passed: False
    # message: "语义相似度 0.72 < 阈值 0.85"
    # details: {"similarity": 0.72, "threshold": 0.85}
```

#### 5.2.6 语义相似度实现

```python
class SemanticSimilarityChecker:
    def __init__(self, llm_client: LLMClient)
    
    async def check(
        answer: str,
        reference: str,
        threshold: float
    ) -> Tuple[float, bool]:
        # 方案 1: 使用 LLM 评估
        # 方案 2: 使用 Embedding 模型计算余弦相似度
        pass
```

---

### 5.3 ReportGenerator（报告生成器扩展示例）

#### 5.3.1 扩展现有报告生成器

```python
class ReportGenerator:
    # 扩展现有类，增加方法
    
    # 生成 HTML 报告
    def generate_html_report(
        self,
        results: TestResults,
        template: str = "default"
    ) -> str
    
    # 生成控制台摘要
    def generate_console_summary(
        self,
        results: TestResults
    ) -> str
    
    # 导出 JSON 结果
    def export_json(
        self,
        results: TestResults,
        output_path: str
    ) -> str
```

#### 5.3.2 HTML 报告模板

```html
<!-- templates/report.html -->
<!DOCTYPE html>
<html>
<head>
    <title>SensePedia 测试报告</title>
    <style>
        .pass { color: green; }
        .fail { color: red; }
        .summary { background: #f5f5f5; padding: 20px; }
    </style>
</head>
<body>
    <h1>测试报告</h1>
    <div class="summary">
        <p>总用例：{{ total }}</p>
        <p>通过：{{ passed }} ({{ pass_rate }})</p>
        <p>失败：{{ failed }}</p>
    </div>
    <!-- 详细结果 -->
</body>
</html>
```

---

## 6. 数据流设计

### 6.1 测试用例生成流程

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│  源文档/API   │ ──▶ │  TestCase     │ ──▶ │  YAML/Excel  │
│  /知识库      │     │  Generator    │     │  测试用例    │
└──────────────┘     └───────────────┘     └──────────────┘
       │                     │
       │ 1. 读取内容         │
       │ 2. 调用 LLM 生成      │
       │ 3. 格式化输出        │
```

### 6.2 测试执行流程

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│  测试用例    │ ──▶ │  AutoTest     │ ──▶ │  QADriver/   │
│  YAML        │     │  Agent        │     │  HttpClient  │
└──────────────┘     └───────────────┘     └──────────────┘
                            │
                            ▼
                     ┌───────────────┐
                     │  TestCase     │
                     │  (执行结果)    │
                     └───────────────┘
```

### 6.3 断言执行流程

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│  测试执行    │ ──▶ │  Assertion    │ ──▶ │  断言结果    │
│  结果        │     │  Engine       │     │  Pass/Fail   │
└──────────────┘     └───────────────┘     └──────────────┘
                            │
                            │ 1. 加载断言规则
                            │ 2. 逐项执行断言
                            │ 3. 汇总结果
                            ▼
                     ┌───────────────┐
                     │ AssertionResult│
                     └───────────────┘
```

### 6.4 报告生成流程

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│  测试+断言   │ ──▶ │  Report       │ ──▶ │  MD/HTML/    │
│  结果        │     │  Generator    │     │  Console     │
└──────────────┘     └───────────────┘     └──────────────┘
```

---

## 7. 配置设计

### 7.1 新增配置文件

```yaml
# config/generator.yaml - 测试用例生成配置
llm:
  provider: "anthropic"  # 或 "openai", "azure"
  model: "claude-sonnet-4-6"
  api_key_env: "ANTHROPIC_API_KEY"
  
generation:
  default_count: 50      # 默认生成用例数
  max_count: 200         # 最大生成用例数
  temperature: 0.7       # LLM 温度
```

```yaml
# config/assertions.yaml - 断言配置（见 5.2.4）
```

### 7.2 配置加载

```python
# src/core/config.py 扩展
@dataclass
class GeneratorConfig:
    llm_provider: str
    llm_model: str
    default_count: int
    
@dataclass  
class AssertionConfig:
    rules: List[AssertionRule]
    
@dataclass
class Config:
    # ... 现有字段
    generator: GeneratorConfig = None
    assertions: AssertionConfig = None
```

---

## 8. CLI 接口设计

### 8.1 命令参数

```python
# main.py 扩展
parser.add_argument("--generate", action="store_true", help="生成测试用例")
parser.add_argument("--generate-from-kb", action="store_true", help="从知识库生成")
parser.add_argument("--execute", action="store_true", help="执行测试")
parser.add_argument("--assert-only", action="store_true", help="仅执行断言")
parser.add_argument("--report", action="store_true", help="生成报告")

parser.add_argument("--source", type=str, help="源文件路径")
parser.add_argument("--testset", type=str, help="测试用例文件")
parser.add_argument("--assertions", type=str, help="断言规则文件")
parser.add_argument("--results", type=str, help="测试结果文件")
parser.add_argument("--output", type=str, help="输出文件路径")
parser.add_argument("--format", type=str, help="报告格式 (md/html/console)")
parser.add_argument("--scenario", type=str, help="场景名称")
parser.add_argument("--count", type=int, help="生成用例数量")
```

### 8.2 使用示例

```bash
# 1. 从 PDF 文档生成测试用例
python main.py --generate \
  --source "docs/requirements.pdf" \
  --output "tests/cases.yaml" \
  --count 50

# 2. 从知识库生成测试用例
python main.py --generate-from-kb \
  --scenario hk_customs \
  --output "tests/kb_cases.yaml" \
  --count 30

# 3. 执行测试
python main.py --execute \
  --testset "tests/cases.yaml" \
  --scenario hk_customs \
  --output "tests/results.json"

# 4. 执行测试并断言
python main.py --execute \
  --testset "tests/cases.yaml" \
  --assertions "tests/assertions.yaml" \
  --scenario hk_customs \
  --output "tests/results.json"

# 5. 生成报告
python main.py --report \
  --results "tests/results.json" \
  --format md \
  --output "reports/report.md"

python main.py --report \
  --results "tests/results.json" \
  --format html \
  --output "reports/report.html"

# 6. 控制台快速查看
python main.py --report \
  --results "tests/results.json" \
  --format console
```

---

## 9. 实现计划

### 9.1 阶段划分

| 阶段 | 内容 | 周期 | 交付物 |
|------|------|------|--------|
| 阶段 1 | TestCaseGenerator | 1 周 | 测试用例生成模块 |
| 阶段 2 | AssertionEngine | 1 周 | 断言引擎模块 |
| 阶段 3 | ReportGenerator 扩展 | 3 天 | HTML/控制台报告 |
| 阶段 4 | CLI 集成 + 测试 | 3 天 | 完整 CLI 工具 |
| 阶段 5 | 文档 + 评审 | 2 天 | 用户手册 |

### 9.2 详细任务

#### 阶段 1: TestCaseGenerator (1 周)

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 设计 LLM Prompt 模板 | P0 | 测试用例生成 Prompt |
| 实现文档解析器 | P0 | PDF/Word/Markdown |
| 实现 TestCaseGenerator | P0 | 核心生成逻辑 |
| 实现 YAML 输出 | P0 | 测试用例格式化 |
| 单元测试 | P1 | 覆盖核心逻辑 |

#### 阶段 2: AssertionEngine (1 周)

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 定义断言类型枚举 | P0 | 5 种断言类型 |
| 实现功能断言 | P0 | contains/not_contains/response_time |
| 实现语义相似度 | P1 | LLM 评估或 Embedding |
| 实现知识溯源 | P1 | citations 检查 |
| 单元测试 | P1 | 覆盖所有断言类型 |

#### 阶段 3: ReportGenerator 扩展 (3 天)

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 实现 HTML 模板 | P0 | Jinja2 模板 |
| 实现 HTML 报告生成 | P0 | 渲染模板 |
| 实现控制台摘要 | P0 | 格式化输出 |
| 实现 JSON 导出 | P1 | 结果序列化 |

#### 阶段 4: CLI 集成 (3 天)

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 扩展 CLI 参数 | P0 | 新增命令支持 |
| 集成 TestCaseGenerator | P0 | --generate 命令 |
| 集成 AssertionEngine | P0 | --assertions 支持 |
| 集成 ReportGenerator | P0 | --report 命令 |
| 端到端测试 | P0 | 完整流程测试 |

#### 阶段 5: 文档 + 评审 (2 天)

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 用户手册 | P0 | CLI 使用说明 |
| API 文档 | P1 | 模块接口说明 |
| 方案评审 | P0 | 团队评审会议 |

---

## 10. 风险与依赖

### 10.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| LLM 生成用例质量不稳定 | 高 | 中 | Prompt 优化 + 人工审核 |
| 语义相似度评估不准确 | 中 | 中 | 多种方法对比验证 |
| 文档解析格式兼容性问题 | 中 | 中 | 逐步支持主流格式 |

### 10.2 依赖

| 依赖 | 用途 | 替代方案 |
|------|------|----------|
| LLM API (Anthropic/OpenAI) | 测试用例生成、语义评估 | 本地部署模型 |
| openpyxl | Excel 读写 | 已有依赖 |
| PyPDF2 / python-docx | 文档解析 | 已有或新增 |
| Jinja2 | HTML 模板渲染 | 新增依赖 |

### 10.3 假设条件

1. 目标系统 API 保持不变（endpoints.yaml 中定义的接口）
2. LLM API 可用且响应时间在可接受范围内
3. 测试团队有基本的 Python 环境

---

## 附录

### A. 术语表

| 术语 | 说明 |
|------|------|
| TestCase | 测试用例，包含问题、预期答案、断言规则 |
| Assertion | 断言，验证测试结果是否符合预期 |
| QADriver | 问答测试驱动器，执行知识库问答测试 |
| DocumentDriver | 文档上传驱动器，执行文档上传操作 |

### B. 参考文档

- 现有框架代码：`src/agents/test_agent.py`
- 配置示例：`config/scenarios.yaml`, `config/endpoints.yaml`
- 测试脚本：`tests/batch_knowledge_chat.py`

### C. 变更记录

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|----------|------|
| 2026-04-07 | 1.0 | 初始草案 | Auto |
