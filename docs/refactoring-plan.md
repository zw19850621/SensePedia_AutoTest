# SensePedia 自动化测试框架 - 重构计划

> 创建时间: 2026-04-10
> 状态: 需求收集中

---

## 一、项目现状

### 1.1 当前架构

```
main.py                    # CLI 入口 (argparse + Agent 混合)
src/
  core/
    config.py              # 配置加载 (181行)
    auth.py                # 认证管理 (142行)
    client.py              # HTTP 客户端 (87行)
  drivers/
    document_driver.py     # 文档上传 (548行)
    qa_driver.py           # 问答测试 (1071行) - 职责过重
  agents/
    test_agent.py          # 自然语言解析 + 编排 (385行)
  reporters/
    report_generator.py    # 报告生成 (312行)
scripts/
  document_test.py         # 文档上传独立脚本
  qa_test.py               # 问答测试独立脚本
config/
  auth.yaml                # 认证凭据
  endpoints.yaml           # API 端点定义
  scenarios.yaml           # 测试场景配置
  rules.yaml               # 规则配置
```

### 1.2 代码规模

| 模块 | 行数 | 状态 |
|------|------|------|
| qa_driver.py | 1071 | 职责混杂（业务+Excel+API） |
| document_driver.py | 548 | 基本合理 |
| test_agent.py | 385 | 混合自然语言解析 + 编排 |
| report_generator.py | 312 | - |
| config.py | 181 | - |
| client.py | 87 | 功能简单 |
| auth.py | 142 | - |

### 1.3 已知问题

- [ ] `qa_driver.py` 文件过长，混杂了测试流程、Excel 读写、文档名称查询等多种职责
- [ ] `save_results_to_excel` 是异步方法但承担了纯同步的 Excel 写入工作
- [ ] 自然语言解析（test_agent）意图识别依赖正则，脆弱且难扩展
- [ ] 存在双入口（main.py + scripts/*.py），功能重叠
- [ ] Excel 结果和 Markdown 报告分离保存，缺乏统一管理
- [ ] 错误处理不统一，部分地方直接 raise，部分返回失败结果
- [ ] 缺少统一的日志配置
- [ ] 根目录存在遗留文件（123.py, test_framework.py, test_qa_debug.py）
- [ ] 根目录 `rules.yaml` 加载但未使用

---

## 二、重构目标

> 请在此处填写你的重构目标

- [ ] 示例：明确项目定位（纯脚本工具 vs 框架 vs Agent 驱动）
- [ ] 示例：减少单文件行数，职责拆分
- [ ] 示例：统一执行入口，消除冗余

### 2.1 核心诉求

_在此填写你最在意的点，例如：_
- 代码结构清晰，新人能快速看懂
- 易于添加新测试类型（如文档编辑、权限测试）
- 报告输出统一、美观
- ...

---

## 三、重构方案选项

### 3.1 入口层

> 当前状态：main.py（Agent 模式）和 scripts/（脚本模式）并存

**选项 A：保留双入口**
- main.py 继续支持自然语言（通过 Agent）
- scripts/ 作为轻量级脚本入口
- 抽取公共逻辑到独立模块，避免重复

**选项 B：统一为脚本入口**
- 移除 main.py 的 Agent 自然语言逻辑
- 所有执行通过 scripts/*.py
- 保留 argparse 支持场景选择

**选项 C：统一为 Agent 入口**
- scripts/ 仅保留极简 wrapper
- 所有逻辑通过 main.py 的 Agent 执行

> 你的选择：____ 理由：____

### 3.2 qa_driver.py 职责拆分

> 当前状态：1071 行，包含测试流程 + Excel 写入 + 文档查询

**选项 A：拆分为 Driver + Exporter**
```
drivers/qa_driver.py          # 纯测试流程（~400行）
exporters/excel_exporter.py   # Excel 导出（~300行）
exporters/doc_resolver.py     # 文档名称解析（~100行）
```

**选项 B：拆分为核心 + 扩展**
```
drivers/qa_core.py            # 核心测试流程
drivers/qa_report.py          # 报告生成（Excel）
```

**选项 C：不拆分，仅内部重构**
- 保持单文件
- 提取内部私有方法到独立类

> 你的选择：____ 理由：____

### 3.3 配置管理

> 当前状态：config.py 中 Config 类同时是数据容器 + 加载逻辑

**选项 A：拆分加载与数据**
```
config/models.py              # 纯数据类（dataclass）
config/loader.py              # YAML 加载逻辑
```

**选项 B：保持现状，仅优化**

> 你的选择：____ 理由：____

### 3.4 错误处理策略

> 当前状态：部分 raise Exception，部分返回失败结果对象

**选项 A：统一使用异常**
- Driver 方法出错时 raise 自定义异常
- 调用方统一 try/except 包装为结果对象

**选项 B：统一使用结果对象**
- 所有方法返回 Result/Err 类型
- 不使用 raise

**选项 C：保持现状**

> 你的选择：____ 理由：____

### 3.5 自然语言 Agent 去留

> 当前状态：test_agent.py 使用正则解析自然语言意图

**选项 A：移除自然语言解析**
- 移除 test_agent.py
- main.py 简化为 argparse wrapper

**选项 B：重构意图识别**
- 使用更健壮的方式（如 LLM intent classification）
- 保留自然语言入口

**选项 C：保留现状**

> 你的选择：____ 理由：____

---

## 四、目录结构规划

> 请在此处描述你期望的最终目录结构

```
示例目标结构：

sensepedia-autotest/
├── main.py                      # 统一入口 (argparse)
├── config/
│   ├── auth.yaml
│   ├── endpoints.yaml
│   └── scenarios.yaml
├── src/
│   ├── core/
│   │   ├── config.py            # 配置加载
│   │   ├── auth.py              # 认证管理
│   │   └── client.py            # HTTP 客户端
│   ├── drivers/
│   │   ├── document_driver.py   # 文档上传
│   │   └── qa_driver.py         # 问答测试（精简后）
│   ├── exporters/
│   │   ├── excel_exporter.py    # Excel 导出
│   │   ├── doc_resolver.py      # 文档名称解析
│   │   └── report_generator.py  # Markdown 报告
│   └── utils/
│       └── ...
├── scripts/
│   ├── upload.py                # 文档上传快捷脚本
│   └── qa_test.py               # 问答测试快捷脚本
├── tests/                       # 单元测试
└── docs/                        # 文档
```

> 你的期望：____

---

## 五、特殊需求

> 请在此处填写你的特殊需求或约束

- [ ] 示例：必须保持对现有测试集的兼容
- [ ] 示例：重构期间不能影响正在进行的测试任务
- [ ] 示例：需要添加 type hints
- [ ] 示例：需要添加单元测试
- [ ] 示例：需要支持多环境（开发/测试/生产）
- [ ] 示例：需要支持 CI/CD 集成
- [ ] ...

---

## 六、重构步骤规划

> 填写完上述内容后，这里会自动生成具体步骤

### Phase 1: 基础清理
- [ ] 删除遗留文件（123.py, test_framework.py, test_qa_debug.py）
- [ ] 统一日志配置
- [ ] ...

### Phase 2: 核心重构
- [ ] 拆分 qa_driver.py
- [ ] ...

### Phase 3: 入口统一
- [ ] ...

### Phase 4: 验证
- [ ] 运行现有测试确保功能不变
- [ ] ...

---
