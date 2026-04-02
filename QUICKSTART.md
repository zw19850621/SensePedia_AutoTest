# 快速开始指南

## 1. 安装依赖

```bash
cd D:\测试项目\Sensepedia\SensePedia_AutoTest
pip install -r requirements.txt
```

## 2. 配置测试场景

编辑 `config/scenarios.yaml`，根据你的实际需求修改：

```yaml
scenarios:
  hk_customs:
    name: "香港海关知识库测试"
    description: "海关 POC 全量测试"
    enabled: true

    document_upload:
      enabled: true
      # 修改为你的文档目录路径
      base_path: "D:\\测试项目\\Sensepedia\\项目版本\\海关 POC\\香港海关文本库文档\\现场环境全量同步 (1219)"
      file_types: ["pdf", "docx", "md", "txt"]
      language: "zh-cn"
      visibility: "private"
      max_concurrent: 3

    qa_test:
      enabled: false  # 暂时不启用问答测试
      testset_path: "D:\\测试项目\\Sensepedia\\项目版本\\海关 POC\\测试集\\测试集样例.xlsx"
      question_column: 2
```

## 3. 配置认证信息

编辑 `config/auth.yaml`：

```yaml
auth:
  credentials:
    username: "admin"
    password: "changeme"  # 如果密码已修改，请更新
```

## 4. 运行测试

### 方式 1: 使用自然语言命令（推荐）

```bash
# 执行完整测试（上传 + 问答）
python main.py "帮我测试香港海关知识库"

# 仅执行文档上传
python main.py "上传香港海关的文档"

# 仅执行问答测试
python main.py "测试海关知识库的问答"
```

### 方式 2: 使用命令行参数

```bash
# 执行完整测试
python main.py --scenario hk_customs

# 仅执行文档上传
python main.py --upload --scenario hk_customs

# 仅执行问答测试
python main.py --qa --scenario hk_customs

# 直接指定文档目录
python main.py --upload --path "D:\\我的文档"

# 直接指定测试集
python main.py --qa --testset "D:\\tests\\questions.xlsx"
```

### 方式 3: Python 代码调用

```python
import asyncio
from src.agents import AutoTestAgent

async def run_test():
    agent = AutoTestAgent()
    
    # 使用自然语言命令
    result = await agent.execute("帮我测试香港海关知识库")
    print(f"结果：{result.message}")
    print(f"报告：{result.report_path}")

asyncio.run(run_test())
```

## 5. 查看测试报告

测试报告保存在 `reports/` 目录下：

```bash
# 报告路径示例
reports/hk_customs/2026-04-01-12-30-00.md
```

报告内容包括：
- 总体统计（成功率、耗时）
- 按文件类型统计（PDF、DOCX、MD、TXT）
- 失败详情和错误原因
- 回答详情（含引用来源）

## 6. 常见问题

### Q: 如何修改测试的并发数？

A: 编辑 `config/scenarios.yaml`，修改 `max_concurrent` 参数：

```yaml
document_upload:
  max_concurrent: 5  # 同时上传 5 个文件
```

### Q: 如何添加新的测试场景？

A: 在 `config/scenarios.yaml` 中添加新场景：

```yaml
scenarios:
  my_new_test:
    name: "我的测试场景"
    document_upload:
      base_path: "D:\\我的文档"
      file_types: ["pdf"]
```

然后运行：
```bash
python main.py --scenario my_new_test
```

### Q: 文档上传失败怎么办？

A: 检查以下几点：
1. 确认 `base_path` 路径存在且包含文件
2. 确认文件格式在 `file_types` 列表中
3. 确认网络连接正常，API 端点可访问
4. 查看报告中的错误信息

### Q: 如何修改轮询间隔和超时时间？

A: 编辑 `config/rules.yaml`：

```yaml
rules:
  document_upload:
    poll_interval: 2    # 轮询间隔（秒）
    poll_timeout: 600   # 超时时间（秒）
```

## 7. 完整测试流程说明

文档上传的完整流程：

1. **上传文档** → 调用 `POST /v1/knowledge/documents/upload`
2. **轮询等待** → 每 2 秒查询一次文档状态
3. **发布文档** → 调用 `POST /v1/knowledge/documents/{id}/publish`
4. **轮询等待** → 每 2 秒查询一次，直到状态为 `published`

问答测试流程：

1. **读取测试集** → 从 Excel 文件读取问题列表
2. **并发提问** → 同时发送多个问题请求
3. **记录响应** → 记录答案、响应时间、引用
4. **生成报告** → 统计成功率、响应时间等指标

---

现在你可以开始使用自动化测试框架了！

有任何问题，请查看 `README.md` 或联系开发团队。
