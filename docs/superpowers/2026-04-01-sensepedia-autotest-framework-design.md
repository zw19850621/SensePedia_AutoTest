# SensePedia 自动化测试框架设计文档

**版本**: 1.0  
**日期**: 2026-04-01  
**状态**: 已批准

---

## 1. 概述

### 1.1 项目背景

本框架为 SensePedia 知识管理系统提供自动化测试能力，主要覆盖：
- **知识文档入库**：文件上传、解析、向量化、入库
- **知识库问答**：检索、回答生成、引用标注

### 1.2 设计目标

1. **数据驱动**：测试数据与测试逻辑分离，通过配置文件管理测试场景
2. **Agent 驱动**：支持自然语言命令触发测试执行
3. **端到端测试**：模拟真实用户路径，覆盖完整业务流程
4. **可扩展**：易于添加新的测试场景和评估规则

### 1.3 约束条件

- 测试运行在现有开发环境（无独立测试环境）
- 需要 JWT 认证访问受保护的 API
- 资源有限，需高效利用现有服务

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      AutoTest Agent                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ 自然语言解析  │  │ 场景匹配器   │  │ 测试执行引擎         │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      配置管理层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ 测试场景配置  │  │ API 端点配置  │  │ 认证配置             │  │
│  │ scenarios.yaml│  │ endpoints.yaml│  │ auth.yaml           │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      测试执行层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ 认证管理器   │  │ 文档上传测试 │  │ 知识库问答测试       │  │
│  │ AuthManager  │  │ UploadTester │  │ QATester             │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │ 数据驱动器   │  │ 报告生成器   │                            │
│  │ DataDriver   │  │ ReportGenerator                           │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      被测系统                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ platform-api │  │  KIA Agent   │  │   RAG Agent          │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件职责

| 组件 | 职责 |
|------|------|
| **AutoTest Agent** | 解析自然语言命令，匹配测试场景，编排测试执行流程 |
| **配置管理** | 加载和管理测试场景、API 端点、认证配置 |
| **AuthManager** | 处理登录、token 获取和刷新 |
| **DocumentDriver** | 执行文档上传测试，支持批量上传 |
| **QADriver** | 执行知识库问答测试，支持批量问答 |
| **ReportGenerator** | 生成测试报告（HTML/Markdown） |
| **RuleEvaluator** | 基于规则评估测试结果 |
| **LLMEvaluator** | 基于 LLM 评估答案质量 |

---

## 3. 目录结构

```
d:\测试项目\Sensepedia\SensePedia_AutoTest\
├── config/
│   ├── scenarios.yaml          # 测试场景配置
│   ├── endpoints.yaml          # API 端点配置
│   ├── auth.yaml               # 认证配置
│   └── rules.yaml              # 成功标准规则
├── data/
│   ├── documents/              # 待上传文档目录（或外部路径引用）
│   └── testsets/               # 问答测试集 Excel 文件
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # 配置加载
│   │   ├── auth.py             # 认证管理
│   │   └── client.py           # HTTP 客户端
│   ├── drivers/
│   │   ├── __init__.py
│   │   ├── document_driver.py  # 文档上传驱动器
│   │   └── qa_driver.py        # 问答测试驱动器
│   ├── agents/
│   │   ├── __init__.py
│   │   └── test_agent.py       # AutoTest Agent
│   ├── reporters/
│   │   ├── __init__.py
│   │   └── report_generator.py # 报告生成
│   └── evaluators/
│       ├── __init__.py
│       ├── rule_evaluator.py   # 规则评估
│       └── llm_evaluator.py    # LLM 质量评估
├── tests/
│   ├── __init__.py
│   ├── test_upload.py          # 上传测试用例
│   └── test_qa.py              # 问答测试用例
├── reports/
│   └── YYYY-MM-DD-HH-mm-ss/    # 测试报告输出
├── main.py                     # 入口
└── requirements.txt
```

---

## 4. 配置设计

### 4.1 测试场景配置 (scenarios.yaml)

```yaml
scenarios:
  hk_customs:
    name: "香港海关知识库测试"
    description: "海关 POC 全量测试"
    enabled: true
    
    document_upload:
      enabled: true
      base_path: "D:\\测试项目\\Sensepedia\\项目版本\\海关 POC\\香港海关文本库\\待上传"
      file_types: ["pdf", "docx", "md", "txt"]
      knowledge_base_id: "kb-hk-customs"
      max_concurrent: 5  # 并发上传数量
    
    qa_test:
      enabled: true
      testset_path: "D:\\测试项目\\Sensepedia\\项目版本\\海关 POC\\测试集\\测试集样例.xlsx"
      question_column: 2      # 第 2 列是问题
      expected_answer_column: 3  # 可选：第 3 列是期望答案
      knowledge_base_id: "kb-hk-customs"
      max_concurrent: 3  # 并发问答数量
```

### 4.2 API 端点配置 (endpoints.yaml)

```yaml
base_urls:
  platform_api: "http://10.210.0.61:8022"
  kia_agent: "http://10.210.0.61:8002"
  rag_agent: "http://10.210.0.61:8003"

endpoints:
  auth_login:
    method: "POST"
    path: "/v1/auth/login"
    base: "platform_api"
    body:
      username: "{username}"
      password: "{password}"
    response:
      token_field: "token"
  
  document_upload:
    mode: "platform_api"  # 或 "kia_direct"
    method: "POST"
    path: "/v1/knowledge/documents/upload"
    base: "platform_api"
    content_type: "multipart/form-data"
  
  knowledge_qa:
    mode: "rag_direct"  # 或 "platform_api"
    method: "POST"
    path: "/execute"
    base: "rag_agent"
    body:
      tool: "rag_query"
      action: "rag_query"
      params:
        query: "{query}"
        knowledge_base_id: "{knowledge_base_id}"
        top_k: 5
```

### 4.3 认证配置 (auth.yaml)

```yaml
auth:
  login_endpoint: "auth_login"  # 引用 endpoints.yaml
  
  credentials:
    username: "admin"
    password: "changeme"
  
  token:
    storage: "memory"  # 或 "file"
    refresh_threshold: 300  # token 过期前 300 秒刷新
```

### 4.4 成功标准规则 (rules.yaml)

```yaml
rules:
  document_upload:
    success_rate:
      min: 0.95  # 95% 成功率
    file_type_success:
      pdf:
        min: 0.90
      docx:
        min: 0.90
      md:
        min: 0.95
    vector_count:
      min_per_document: 10  # 每文档至少 10 个向量
  
  qa_test:
    success_rate:
      min: 0.90  # 90% 回答成功率
    response_time:
      avg_max: 5.0  # 平均响应时间<5s
      p95_max: 8.0  # P95<8s
      p99_max: 10.0  # P99<10s
    answer_quality:
      llm_score_min: 3.5  # LLM 评分>=3.5/5.0
    citation_accuracy:
      min: 0.85  # 引用准确率>=85%
```

---

## 5. 核心接口设计

### 5.1 AuthManager

```python
class AuthManager:
    """认证管理器 - 处理登录、token 获取和刷新"""
    
    def __init__(self, config: AuthConfig):
        """初始化认证管理器"""
        ...
    
    async def login(self, username: str, password: str) -> str:
        """
        登录获取 JWT token
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            JWT token 字符串
        """
        ...
    
    async def get_valid_token(self) -> str:
        """
        获取有效 token（自动刷新）
        
        Returns:
            有效的 JWT token
        """
        ...
    
    async def refresh_token(self) -> str:
        """刷新 token"""
        ...
```

### 5.2 DocumentDriver

```python
class DocumentDriver:
    """文档上传驱动器 - 执行文档上传测试"""
    
    def __init__(self, config: Config, auth_manager: AuthManager):
        """初始化驱动器"""
        ...
    
    async def upload_document(self, file_path: str, kb_id: str) -> UploadResult:
        """
        上传单个文档
        
        Args:
            file_path: 文件路径
            kb_id: 知识库 ID
            
        Returns:
            UploadResult 包含上传结果
        """
        ...
    
    async def batch_upload(self, file_paths: list[str], kb_id: str) -> BatchUploadResult:
        """
        批量上传文档
        
        Args:
            file_paths: 文件路径列表
            kb_id: 知识库 ID
            
        Returns:
            BatchUploadResult 包含批量上传结果
        """
        ...
```

### 5.3 QADriver

```python
class QADriver:
    """问答测试驱动器 - 执行知识库问答测试"""
    
    def __init__(self, config: Config, auth_manager: AuthManager):
        """初始化驱动器"""
        ...
    
    async def ask(self, query: str, kb_id: str) -> QAResult:
        """
        单次问答
        
        Args:
            query: 问题
            kb_id: 知识库 ID
            
        Returns:
            QAResult 包含回答、响应时间、引用等
        """
        ...
    
    async def batch_ask(self, questions: list[str], kb_id: str) -> list[QAResult]:
        """
        批量问答
        
        Args:
            questions: 问题列表
            kb_id: 知识库 ID
            
        Returns:
            QAResult 列表
        """
        ...
```

### 5.4 ReportGenerator

```python
class ReportGenerator:
    """报告生成器 - 生成测试报告"""
    
    def __init__(self, config: Config):
        """初始化报告生成器"""
        ...
    
    def generate_upload_report(self, result: BatchUploadResult) -> str:
        """
        生成文档上传报告
        
        Args:
            result: 批量上传结果
            
        Returns:
            Markdown 格式报告
        """
        ...
    
    def generate_qa_report(self, results: list[QAResult]) -> str:
        """
        生成问答测试报告
        
        Args:
            results: 问答结果列表
            
        Returns:
            Markdown 格式报告
        """
        ...
    
    def generate_full_report(self, upload_result: BatchUploadResult, 
                             qa_results: list[QAResult]) -> str:
        """
        生成完整测试报告
        
        Returns:
            Markdown 格式完整报告
        """
        ...
```

### 5.5 AutoTestAgent

```python
class AutoTestAgent:
    """AutoTest Agent - 自然语言驱动的测试执行引擎"""
    
    def __init__(self, config: Config):
        """初始化 Agent"""
        ...
    
    async def execute(self, command: str) -> TestExecutionResult:
        """
        执行自然语言命令
        
        Args:
            command: 自然语言命令，如"帮我测试香港海关知识库"
            
        Returns:
            TestExecutionResult 包含执行结果
        """
        # 1. 解析意图
        intent = self._parse_intent(command)
        
        # 2. 匹配场景
        scenario = self._match_scenario(intent)
        
        # 3. 执行测试
        result = await self._run_tests(scenario)
        
        # 4. 生成报告
        report = self._generate_report(result)
        
        return result
```

---

## 6. AutoTest Agent 工作流程

```
用户输入："帮我测试一下香港海关知识库"
              │
              ▼
┌─────────────────────────────────┐
│ 1. 解析意图                     │
│    - 提取场景关键词             │
│    - 识别操作类型（test/upload/qa）│
└─────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│ 2. 加载场景配置                 │
│    - 读取 scenarios.yaml        │
│    - 匹配场景：hk_customs       │
│    - 获取文档路径、测试集路径    │
└─────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│ 3. 认证管理                     │
│    - 检查 token 是否有效         │
│    - 如过期，调用登录接口刷新    │
└─────────────────────────────────┘
              │
        ┌─────┴─────┐
        ▼           ▼
┌─────────────┐ ┌─────────────┐
│ 4a. 文档上传 │ │ 4b. 问答测试 │
│  - 扫描文件  │ │ - 读取 Excel │
│  - 调用 API  │ │ - 并发提问  │
│  - 记录结果  │ │ - 记录响应  │
└─────────────┘ └─────────────┘
        │           │
        └─────┬─────┘
              ▼
┌─────────────────────────────────┐
│ 5. 结果评估                     │
│    - RuleEvaluator: 规则评估   │
│    - LLMEvaluator: 质量评估    │
└─────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│ 6. 生成报告                     │
│    - 上传成功率、分类统计        │
│    - 问答成功率、响应时间        │
│    - LLM 质量评分、引用准确率    │
│    - 输出 Markdown/HTML 报告     │
└─────────────────────────────────┘
```

---

## 7. 测试报告设计

### 7.1 文档上传报告

| 指标 | 数值 |
|------|------|
| 总文件数 | N |
| 成功上传 | M (X%) |
| 失败文件 | K |
| PDF 解析成功 | A/B |
| DOCX 解析成功 | C/D |
| MD 解析成功 | E/F |
| TXT 解析成功 | G/H |
| 总向量数 | V |
| 平均每文档向量数 | V/N |

### 7.2 问答测试报告

| 指标 | 数值 |
|------|------|
| 总问题数 | N |
| 成功回答 | M (X%) |
| 平均响应时间 | X.Xs |
| P95 响应时间 | X.Xs |
| P99 响应时间 | X.Xs |
| LLM 质量评分 | X.X/5.0 |
| 引用准确率 | XX% |

### 7.3 成功标准判定

**通过条件**（基于 rules.yaml 配置）：
- 文档上传成功率 >= 95%
- 各文件格式解析成功率 >= 90%
- 问答成功率 >= 90%
- 平均响应时间 < 5s
- P95 响应时间 < 8s
- LLM 质量评分 >= 3.5
- 引用准确率 >= 85%

---

## 8. 依赖项

### 8.1 Python 依赖 (requirements.txt)

```
fastapi>=0.104.0
httpx>=0.25.0
pydantic>=2.0.0
pyyaml>=6.0
openpyxl>=3.1.0       # Excel 读取
pandas>=2.0.0         # 数据处理
pytest>=7.4.0         # 测试框架
pytest-asyncio>=0.21.0
```

### 8.2 可选依赖（LLM 评估）

```
openai>=1.0.0         # 或其他 LLM SDK
```

---

## 9. 实施计划

### Phase 1: 基础设施
- [ ] 创建目录结构
- [ ] 实现配置加载模块
- [ ] 实现 HTTP 客户端
- [ ] 实现 AuthManager

### Phase 2: 驱动器实现
- [ ] 实现 DocumentDriver
- [ ] 实现 QADriver
- [ ] 实现数据驱动器（Excel 读取、文件扫描）

### Phase 3: Agent 和报告
- [ ] 实现 AutoTestAgent
- [ ] 实现 ReportGenerator
- [ ] 实现 RuleEvaluator

### Phase 4: 测试和集成
- [ ] 编写单元测试
- [ ] 端到端测试验证
- [ ] 实现 LLMEvaluator（可选）

---

## 10. 附录

### 10.1 测试集 Excel 格式

| 列 1: ID | 列 2: 问题 | 列 3: 期望答案（可选） | 列 4: 知识点（可选） |
|----------|-----------|----------------------|---------------------|
| Q001 | 香港海关的征税范围是什么？ | ... | 征税政策 |
| Q002 | 如何申请进出口许可证？ | ... | 许可证办理 |

### 10.2 API 响应示例

**登录响应**：
```json
{
    "token": "eyJhbGci...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": { ... }
}
```

**文档上传响应**：
```json
{
    "status": "success",
    "document_id": "doc-xxx",
    "job_id": "job-yyy"
}
```

**问答响应**：
```json
{
    "status": "ok",
    "answer": "根据知识库...",
    "citations": [...],
    "response_time_ms": 2300
}
```
