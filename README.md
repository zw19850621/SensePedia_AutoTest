# SensePedia 自动化测试框架

基于自然语言驱动的端到端自动化测试框架，用于测试 SensePedia 知识管理系统的文档入库和知识库问答功能。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置测试场景

编辑 `config/scenarios.yaml`，配置你的测试场景：

```yaml
scenarios:
  hk_customs:
    name: "香港海关知识库测试"
    document_upload:
      enabled: true
      base_path: "D:\\测试项目\\Sensepedia\\项目版本\\海关 POC\\香港海关文本库文档\\现场环境全量同步 (1219)"
      file_types: ["pdf", "docx", "md", "txt"]
    qa_test:
      enabled: true
      testset_path: "D:\\测试项目\\Sensepedia\\项目版本\\海关 POC\\测试集\\测试集样例.xlsx"
      question_column: 2
```

### 3. 配置认证信息

编辑 `config/auth.yaml`：

```yaml
auth:
  credentials:
    username: "admin"
    password: "changeme"
```

### 4. 运行测试

**使用自然语言命令：**
```bash
python main.py "帮我测试香港海关知识库"
```

**仅执行文档上传：**
```bash
python main.py --upload --scenario hk_customs
```

**仅执行问答测试：**
```bash
python main.py --qa --scenario hk_customs
```

## 目录结构

```
SensePedia_AutoTest/
├── config/                 # 配置文件
│   ├── scenarios.yaml      # 测试场景配置
│   ├── endpoints.yaml      # API 端点配置
│   ├── auth.yaml           # 认证配置
│   └── rules.yaml          # 成功标准规则
├── data/                   # 测试数据
│   ├── documents/          # 待上传文档
│   └── testsets/           # 问答测试集
├── src/                    # 源代码
│   ├── core/               # 核心模块
│   ├── drivers/            # 测试驱动器
│   ├── agents/             # AutoTest Agent
│   └── reporters/          # 报告生成器
├── reports/                # 测试报告输出
├── main.py                 # 主入口
└── requirements.txt        # 依赖项
```

## 核心功能

### 文档上传测试

- 支持多种文件格式（PDF、DOCX、MD、TXT）
- 自动轮询等待上传完成
- 自动触发文档解析/发布
- 轮询等待发布完成
- 按文件类型统计成功率

### 知识库问答测试

- 从 Excel 读取测试问题
- 并发执行问答测试
- 统计响应时间（平均、P95、P99）
- 记录引用来源

### AutoTest Agent

支持自然语言命令：
- "帮我测试香港海关知识库" - 执行完整测试
- "上传香港海关的文档" - 仅执行上传
- "测试海关知识库的问答" - 仅执行问答

## 配置说明

### scenarios.yaml

```yaml
scenarios:
  hk_customs:
    name: "香港海关知识库测试"
    enabled: true
    document_upload:
      base_path: "文档目录路径"
      file_types: ["pdf", "docx", "md", "txt"]
      language: "zh-cn"
      visibility: "private"
      max_concurrent: 3
    qa_test:
      testset_path: "测试集 Excel 路径"
      question_column: 2
      knowledge_base_id: ""
      max_concurrent: 3
```

### auth.yaml

```yaml
auth:
  credentials:
    username: "admin"
    password: "changeme"
  token:
    refresh_threshold: 300  # token 过期前 300 秒刷新
```

### rules.yaml

```yaml
rules:
  document_upload:
    success_rate:
      min: 0.95  # 95% 成功率
    poll_interval: 2  # 轮询间隔（秒）
    poll_timeout: 300  # 超时时间（秒）
```

## 测试报告

测试报告生成在 `reports/` 目录下，按场景名称分类：

```
reports/
└── hk_customs/
    └── 2026-04-01-12-30-00.md
```

报告内容包括：
- 总体统计（成功率、耗时）
- 按文件类型统计
- 失败详情
- 回答详情（含引用来源）

## API 接口

测试框架调用的 API 接口配置在 `config/endpoints.yaml`：

- 登录接口：`POST /v1/auth/login`
- 文档上传：`POST /v1/knowledge/documents/upload`
- 文档状态：`GET /v1/knowledge/documents/{document_id}`
- 文档发布：`POST /v1/knowledge/documents/{document_id}/publish`
- 问答接口：`POST /execute`

## 使用示例

### Python 代码调用

```python
import asyncio
from src.agents import AutoTestAgent
from src.core import load_config

async def run_test():
    config = load_config()
    agent = AutoTestAgent(config)
    
    # 方式 1: 使用自然语言命令
    result = await agent.execute("帮我测试香港海关知识库")
    print(f"结果：{result.message}")
    print(f"报告：{result.report_path}")
    
    # 方式 2: 直接调用上传
    upload_result = await agent.upload_documents(
        scenario_name="hk_customs"
    )
    print(f"上传成功率：{upload_result.success_rate:.1%}")
    
    # 方式 3: 直接调用问答
    qa_result = await agent.run_qa_tests(
        scenario_name="hk_customs"
    )
    print(f"问答成功率：{qa_result.success_rate:.1%}")

asyncio.run(run_test())
```

## 扩展开发

### 添加新的测试场景

在 `config/scenarios.yaml` 中添加新场景：

```yaml
scenarios:
  new_scenario:
    name: "新测试场景"
    document_upload:
      base_path: "./data/new_docs"
      file_types: ["pdf"]
```

### 添加新的评估规则

在 `config/rules.yaml` 中添加新规则：

```yaml
rules:
  new_rule:
    some_metric:
      min: 0.90
```

## 故障排查

### 登录失败

检查 `config/auth.yaml` 中的用户名和密码是否正确。

### 文档上传失败

1. 检查文档目录路径是否正确
2. 检查文件格式是否在 `file_types` 列表中
3. 检查网络连接和 API 端点是否可达

### 问答测试失败

1. 检查测试集 Excel 文件路径是否正确
2. 检查问题列号是否正确
3. 检查 RAG Agent 服务是否正常运行

## License

MIT
