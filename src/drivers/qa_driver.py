"""
知识库问答测试驱动器
"""

import asyncio
import time
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..core.config import Config, QATestConfig, EndpointConfig
from ..core.auth import AuthManager
from ..core.client import HttpClient

# 配置日志
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


@dataclass
class SessionInfo:
    """会话信息"""
    session_id: str
    title: str
    pinned: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class MessageInfo:
    """消息信息"""
    message_id: str
    session_id: str
    role: str
    content: str
    created_at: Optional[str] = None


@dataclass
class QAResult:
    """单次问答结果"""
    question: str = ""
    success: bool = False
    answer: Optional[str] = None
    response_time: float = 0.0
    citations: List[dict] = field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    request_details: List[dict] = field(default_factory=list)  # 记录每个接口的请求和响应
    question_id: Optional[str] = None  # 问题编号（从测试集第一列读取）


@dataclass
class BatchQAResult:
    """批量问答结果"""
    total: int = 0
    success: int = 0
    failed: int = 0
    results: List[QAResult] = field(default_factory=list)
    start_time: datetime = None
    end_time: datetime = None

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total == 0:
            return 0.0
        return self.success / self.total

    @property
    def avg_response_time(self) -> float:
        """平均响应时间"""
        successful = [r for r in self.results if r.success]
        if not successful:
            return 0.0
        return sum(r.response_time for r in successful) / len(successful)

    @property
    def p95_response_time(self) -> float:
        """P95 响应时间"""
        successful = sorted([r.response_time for r in self.results if r.success])
        if not successful:
            return 0.0
        index = int(len(successful) * 0.95)
        return successful[min(index, len(successful) - 1)]

    @property
    def p99_response_time(self) -> float:
        """P99 响应时间"""
        successful = sorted([r.response_time for r in self.results if r.success])
        if not successful:
            return 0.0
        index = int(len(successful) * 0.99)
        return successful[min(index, len(successful) - 1)]

    @property
    def duration(self) -> float:
        """总耗时（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class QADriver:
    """问答测试驱动器 - 执行知识库问答测试"""

    def __init__(self, config: Config, auth_manager: AuthManager):
        """
        初始化驱动器

        Args:
            config: 配置对象
            auth_manager: 认证管理器
        """
        self.config = config
        self.auth_manager = auth_manager

    def _get_endpoint(self, name: str) -> Optional[EndpointConfig]:
        """获取指定名称的端点配置"""
        return self.config.get_endpoint(name)

    def _format_path(self, path: str, **kwargs) -> str:
        """格式化路径中的占位符"""
        for key, value in kwargs.items():
            path = path.replace(f"{{{key}}}", str(value))
        return path

    def _build_body(self, endpoint: EndpointConfig, **kwargs) -> dict:
        """根据端点配置构建请求体"""
        body = {}
        if endpoint.body:
            for key, value in endpoint.body.items():
                if isinstance(value, str):
                    # 替换占位符
                    body[key] = value.format(**kwargs)
                else:
                    body[key] = value
        return body

    def _add_request_detail(
        self,
        result: QAResult,
        method_name: str,
        method: str,
        path: str,
        request_body: dict,
        response_data: Any,
        elapsed: float,
        status_code: int,
    ):
        """添加请求详情到指定结果"""
        result.request_details.append({
            "api": method_name,
            "method": method,
            "path": path,
            "request_body": request_body,
            "response_data": response_data if isinstance(response_data, (dict, list)) else {"raw": str(response_data)},
            "status_code": status_code,
            "elapsed": f"{elapsed:.3f}s",
        })

    async def create_session(self, title: str = "New Chat", result: QAResult = None) -> SessionInfo:
        """
        创建新会话

        Args:
            title: 会话标题
            result: 用于记录请求详情的结果对象

        Returns:
            SessionInfo 会话信息
        """
        client = None
        start_time = time.time()
        try:
            auth_header = await self.auth_manager.get_auth_header()
            endpoint = self._get_endpoint("rag_create_session")
            if endpoint is None:
                raise Exception("未找到端点配置：rag_create_session，请检查 config/endpoints.yaml")

            client = HttpClient(base_url=self.config.get_base_url(endpoint.base))
            body = self._build_body(endpoint, title=title)

            response = await client.request(
                method=endpoint.method,
                path=endpoint.path,
                headers=auth_header,
                json=body,
            )

            if response.status_code not in [200, 201]:
                raise Exception(f"创建会话失败：{response.status_code} - {response.text}")

            data = response.json()
            elapsed = time.time() - start_time

            # 记录请求详情
            self._add_request_detail(result, "create_session", "POST", "/v1/rag/sessions", body, data, elapsed, response.status_code)

            return SessionInfo(
                session_id=data["session_id"],
                title=data["title"],
                pinned=data.get("pinned", False),
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
            )

        finally:
            if client:
                await client.close()

    async def get_session(self, session_id: str, result: QAResult = None) -> Dict[str, Any]:
        """
        获取会话信息

        Args:
            session_id: 会话 ID
            result: 用于记录请求详情的结果对象

        Returns:
            包含 session 和 messages 的字典
        """
        client = None
        start_time = time.time()
        try:
            auth_header = await self.auth_manager.get_auth_header()
            endpoint = self._get_endpoint("rag_get_session")
            if endpoint is None:
                raise Exception("未找到端点配置：rag_get_session，请检查 config/endpoints.yaml")

            client = HttpClient(base_url=self.config.get_base_url(endpoint.base))
            path = self._format_path(endpoint.path, session_id=session_id)

            response = await client.request(
                method=endpoint.method,
                path=path,
                headers=auth_header,
            )

            if response.status_code != 200:
                raise Exception(f"获取会话失败：{response.status_code} - {response.text}")

            data = response.json()
            elapsed = time.time() - start_time

            # 记录请求详情
            self._add_request_detail(result, "get_session", "GET", path, {}, data, elapsed, response.status_code)

            return data

        finally:
            if client:
                await client.close()

    async def update_session_title(self, session_id: str, title: str, result: QAResult = None) -> SessionInfo:
        """
        更新会话标题

        Args:
            session_id: 会话 ID
            title: 新标题（会自动截取到 50 字符，避免数据库报错）
            result: 用于记录请求详情的结果对象

        Returns:
            SessionInfo 更新后的会话信息
        """
        # 截取 title 到 50 字符（避免数据库字段过长）
        truncated_title = title[:50] if len(title) > 50 else title

        start_time = time.time()
        client = None
        try:
            auth_header = await self.auth_manager.get_auth_header()
            endpoint = self._get_endpoint("rag_update_session")
            if endpoint is None:
                raise Exception("未找到端点配置：rag_update_session，请检查 config/endpoints.yaml")

            client = HttpClient(base_url=self.config.get_base_url(endpoint.base))
            path = self._format_path(endpoint.path, session_id=session_id)
            # 只设置 title 字段，不设置 pinned
            body = {"title": truncated_title}

            response = await client.request(
                method=endpoint.method,
                path=path,
                headers=auth_header,
                json=body,
            )

            if response.status_code != 200:
                logger.error(f"响应内容：{response.text}")
                raise Exception(f"更新会话失败：{response.status_code} - {response.text}")

            data = response.json()
            elapsed = time.time() - start_time

            # 记录请求详情
            self._add_request_detail(result, "update_session_title", "PATCH", path, body, data, elapsed, response.status_code)

            session_info = SessionInfo(
                session_id=data["session_id"],
                title=data["title"],
                pinned=data.get("pinned", False),
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
            )
            return session_info

        finally:
            if client:
                await client.close()

    async def create_message(
        self,
        session_id: str,
        content: str,
        knowledge_base_id: str = "ALL_KB",
        scope_mode: str = "all",
        result: QAResult = None,
    ) -> MessageInfo:
        """
        创建提问消息

        Args:
            session_id: 会话 ID
            content: 问题内容
            knowledge_base_id: 知识库 ID
            scope_mode: 范围模式
            result: 用于记录请求详情的结果对象

        Returns:
            MessageInfo 消息信息
        """
        start_time = time.time()
        client = None
        try:
            auth_header = await self.auth_manager.get_auth_header()
            endpoint = self._get_endpoint("rag_create_message")
            if endpoint is None:
                raise Exception("未找到端点配置：rag_create_message，请检查 config/endpoints.yaml")

            client = HttpClient(base_url=self.config.get_base_url(endpoint.base))
            path = self._format_path(endpoint.path, session_id=session_id)
            body = self._build_body(
                endpoint,
                content=content,
                knowledge_base_id=knowledge_base_id,
                scope_mode=scope_mode,
            )

            response = await client.request(
                method=endpoint.method,
                path=path,
                headers=auth_header,
                json=body,
            )

            if response.status_code != 201:
                logger.error(f"响应内容：{response.text}")
                raise Exception(f"创建消息失败：{response.status_code} - {response.text}")

            data = response.json()
            elapsed = time.time() - start_time

            # 记录请求详情
            self._add_request_detail(result, "create_message", "POST", path, body, data, elapsed, response.status_code)

            message_info = MessageInfo(
                message_id=data["message_id"],
                session_id=data["session_id"],
                role=data["role"],
                content=data["content"],
                created_at=data.get("created_at"),
            )
            return message_info

        finally:
            if client:
                await client.close()

    async def create_assistant_message(
        self,
        session_id: str,
        answer: str,
        citations: List[dict],
        knowledge_base_id: str = "ALL_KB",
        scope_mode: str = "all",
        result: QAResult = None,
    ) -> MessageInfo:
        """
        步骤 6：创建助手回复消息（更新提问）

        Args:
            session_id: 会话 ID
            answer: 步骤 5 生成的答案
            citations: 步骤 5 流式响应中 event=done 返回的 citations
            knowledge_base_id: 知识库 ID
            scope_mode: 范围模式
            result: 用于记录请求详情的结果对象

        Returns:
            MessageInfo 消息信息
        """
        start_time = time.time()
        client = None
        try:
            auth_header = await self.auth_manager.get_auth_header()
            # 使用与步骤 4 相同的端点配置
            endpoint = self._get_endpoint("rag_create_message")
            if endpoint is None:
                raise Exception("未找到端点配置：rag_create_message，请检查 config/endpoints.yaml")

            client = HttpClient(base_url=self.config.get_base_url(endpoint.base))
            path = self._format_path(endpoint.path, session_id=session_id)

            # 构建请求体：role="assistant"，其他参数与步骤 4 相同
            body = {
                "role": "assistant",
                "content": answer,
                "citations": citations,
                "scope_mode": scope_mode,
                "knowledge_base_id": knowledge_base_id,
                "doc_ids": [],
                "chat_mode": "pipeline",
            }

            response = await client.request(
                method=endpoint.method,
                path=path,
                headers=auth_header,
                json=body,
            )

            if response.status_code != 201:
                logger.error(f"响应内容：{response.text}")
                raise Exception(f"创建助手消息失败：{response.status_code} - {response.text}")

            data = response.json()
            elapsed = time.time() - start_time

            # 记录请求详情
            self._add_request_detail(result, "create_assistant_message", "POST", path, body, data, elapsed, response.status_code)

            message_info = MessageInfo(
                message_id=data["message_id"],
                session_id=data["session_id"],
                role=data["role"],
                content=data["content"],
                created_at=data.get("created_at"),
            )
            return message_info

        finally:
            if client:
                await client.close()

    def _parse_streaming_response(self, lines: List[str]) -> str:
        """
        解析流式响应，拼接所有 token 事件的 delta 字段
        SSE 格式：
          event: token
          data: {"request_id": "...", "delta": "..."}

        Args:
            lines: 流式响应的行列表

        Returns:
            拼接后的完整答案
        """
        answer_parts = []
        token_count = 0
        current_event = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # 解析 SSE 格式：event: xxx 或 data: xxx
            if stripped.startswith("event: "):
                current_event = stripped[7:].strip()
            elif stripped.startswith("data: ") and current_event == "token":
                json_str = stripped[6:].strip()
                try:
                    data = json.loads(json_str)
                    if "delta" in data:
                        answer_parts.append(data["delta"])
                        token_count += 1
                except (json.JSONDecodeError, ValueError) as e:
                    logger.debug(f"解析 data 失败：{json_str[:100]}... 错误：{e}")

        answer = "".join(answer_parts)
        #logger.info(f"解析完成：共 {len(lines)} 行，其中 {token_count} 行 token 事件，拼接后答案长度：{len(answer)}")
        return answer

    async def streaming_query(
        self,
        query: str,
        session_id: str,
        knowledge_base_id: str = "ALL_KB",
        top_k: int = 8,
        rerank: bool = True,
        citation_mode: str = "inline",
    ) -> QAResult:
        """
        流式查询并获取答案

        Args:
            query: 问题
            session_id: 会话 ID
            knowledge_base_id: 知识库 ID
            top_k: 返回的顶部结果数
            rerank: 是否重排序
            citation_mode: 引用模式

        Returns:
            QAResult 问答结果
        """
        result = QAResult(question=query, session_id=session_id)
        client = None

        try:
            auth_header = await self.auth_manager.get_auth_header()
            endpoint = self._get_endpoint("rag_query_stream")
            if endpoint is None:
                raise Exception("未找到端点配置：rag_query_stream，请检查 config/endpoints.yaml")

            # 使用更长的超时时间（流式查询可能需要 2-5 分钟）
            client = HttpClient(
                base_url=self.config.get_base_url(endpoint.base),
                timeout=1200.0,  # 20 分钟超时
            )
            body = self._build_body(
                endpoint,
                query=query,
                session_id=session_id,
                knowledge_base_id=knowledge_base_id,
                top_k=top_k,
                rerank=rerank,
                citation_mode=citation_mode,
            )

            start_time = time.time()

            response = await client.request(
                method=endpoint.method,
                path=endpoint.path,
                headers=auth_header,
                json=body,
            )

            if response.status_code != 200:
                logger.error(f"响应内容：{response.text}")
                result.success = False
                result.error = f"请求失败：{response.status_code} - {response.text}"
                elapsed = time.time() - start_time
                self._add_request_detail(result, "streaming_query", "POST", endpoint.path, body, {"error": response.text}, elapsed, response.status_code)
                return result

            # 收集流式响应行
            lines = []
            async for line in response.aiter_lines():
                if line.strip():
                    lines.append(line)

            result.response_time = time.time() - start_time

            # 解析响应
            answer = self._parse_streaming_response(lines)
            result.answer = answer

            # 提取 metadata 和 citations（从 event: done 的 data 中解析）
            citations = []
            metadata = {}
            in_done_event = False

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("event: done"):
                    in_done_event = True
                elif in_done_event and stripped.startswith("data: "):
                    try:
                        json_str = stripped[6:].strip()
                        data = json.loads(json_str)
                        citations = data.get("citations", [])
                        metadata = data
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.debug(f"解析 done 事件失败：{e}")
                    break
                elif stripped.startswith("event:"):
                    in_done_event = False

            result.citations = citations
            result.metadata = metadata

            # 记录请求详情 - 保存原始流式响应
            elapsed = time.time() - start_time
            raw_response = "\n".join(lines)  # 原始 SSE 格式响应
            self._add_request_detail(result, "streaming_query", "POST", endpoint.path, body, {"raw": raw_response, "answer": answer, "citations": citations, "metadata": metadata}, elapsed, response.status_code)

            result.success = True
            return result

        except Exception as e:
            logger.error(f"流式查询失败：{e}")
            result.success = False
            result.error = str(e)
            return result

        finally:
            if client:
                await client.close()

    async def run_single_qa_test(
        self,
        question: str,
        knowledge_base_id: str = "ALL_KB",
        session_title: str = None,
        question_id: str = None,
    ) -> QAResult:
        """
        执行单次完整的问答测试流程

        Args:
            question: 问题
            knowledge_base_id: 知识库 ID
            session_title: 会话标题（从测试集读取）
            question_id: 问题编号（从测试集第一列读取）

        Returns:
            QAResult 问答结果
        """
        result = QAResult(question=question, question_id=question_id)

        try:
            # 1. 创建新会话
            session_info = await self.create_session("New Chat", result)
            session_id = session_info.session_id
            result.session_id = session_id

            # 2. 获取会话详情（验证会话创建成功）
            await self.get_session(session_id, result)

            # 3. 更新会话标题（如果提供了标题）
            if session_title:
                await self.update_session_title(session_id, session_title, result)

            # 4. 创建提问消息
            message_info = await self.create_message(session_id, question, knowledge_base_id, result=result)
            result.message_id = message_info.message_id

            # 5. 流式查询获取答案
            qa_result = await self.streaming_query(question, session_id, knowledge_base_id)
            result.answer = qa_result.answer
            result.response_time = qa_result.response_time
            result.metadata = qa_result.metadata
            result.citations = qa_result.citations
            result.success = qa_result.success
            result.error = qa_result.error
            # 合并 streaming_query 的请求详情
            result.request_details.extend(qa_result.request_details)

            # 6. 创建助手回复消息（更新提问）
            if qa_result.answer and qa_result.citations is not None:
                await self.create_assistant_message(
                    session_id=session_id,
                    answer=qa_result.answer,
                    citations=qa_result.citations,
                    knowledge_base_id=knowledge_base_id,
                    result=result,
                )

            return result

        except Exception as e:
            result.success = False
            result.error = str(e)
            return result

    async def run_batch_qa_tests(
        self,
        questions: List[tuple],  # [(question, title, question_id), ...]
        knowledge_base_id: str = "ALL_KB",
        max_concurrent: int = 3,
    ) -> BatchQAResult:
        """
        批量执行问答测试

        Args:
            questions: 问题列表，每个元素为 (问题，标题，编号) 元组
            knowledge_base_id: 知识库 ID
            max_concurrent: 最大并发数

        Returns:
            BatchQAResult 批量问答结果
        """
        result = BatchQAResult(start_time=datetime.now())
        result.total = len(questions)

        if result.total == 0:
            result.end_time = datetime.now()
            return result

        logger.info("=" * 60)
        logger.info(f"开始执行问答测试，共 {result.total} 个问题，最大并发数：{max_concurrent}")
        logger.info("=" * 60)

        # 并发控制
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_test_with_semaphore(idx: int, q: tuple) -> QAResult:
            async with semaphore:
                if len(q) >= 3:
                    question, title, question_id = q
                else:
                    question, title = q
                    question_id = None
                logger.info(f"[{idx + 1}/{result.total}] 开始处理：{question[:50]}...")
                qa_result = await self.run_single_qa_test(
                    question=question,
                    knowledge_base_id=knowledge_base_id,
                    session_title=title,
                    question_id=question_id,
                )
                status = "成功" if qa_result.success else "失败"
                logger.info(f"[{idx + 1}/{result.total}] 完成：{status}, 耗时：{qa_result.response_time:.2f}s")
                return qa_result

        # 执行批量测试
        tasks = [run_test_with_semaphore(idx, q) for idx, q in enumerate(questions)]
        results = await asyncio.gather(*tasks)

        # 统计结果
        result.results = list(results)
        result.success = sum(1 for r in results if r.success)
        result.failed = sum(1 for r in results if not r.success)
        result.end_time = datetime.now()

        logger.info("=" * 60)
        logger.info(f"测试完成：成功 {result.success}/{result.total}, 成功率：{result.success_rate:.1%}")
        logger.info(f"平均响应时间：{result.avg_response_time:.2f}s, P95: {result.p95_response_time:.2f}s")
        logger.info("=" * 60)

        return result

    async def load_questions_from_excel(
        self,
        testset_path: str,
        question_column: int = 2,
        title_column: int = None,  # 可选，用于读取标题
        id_column: int = 1,  # 编号列（1-based）
        sheet_name: str = None,  # Excel 工作表名称（None 表示使用默认第一个工作表）
        start_row: int = 2,
        end_row: int = None,
    ) -> List[tuple]:
        """
        从 Excel 文件加载问题列表

        Args:
            testset_path: Excel 文件路径
            question_column: 问题所在列（1-based）
            title_column: 标题所在列（1-based），None 则使用问题作为标题
            id_column: 编号所在列（1-based），默认第 1 列
            sheet_name: Excel 工作表名称（None 表示使用默认第一个工作表）
            start_row: 起始行（1-based），跳过表头
            end_row: 结束行（None 表示到最后）

        Returns:
            问题列表 [(question, title, question_id), ...]
        """
        try:
            import openpyxl
        except ImportError:
            raise ImportError("需要安装 openpyxl: pip install openpyxl")

        wb = openpyxl.load_workbook(testset_path, read_only=True)

        # 根据 sheet_name 获取工作表
        if sheet_name:
            ws = wb[sheet_name]
        else:
            ws = wb.active

        questions = []
        end_row_param = end_row if end_row else ws.max_row

        for row in ws.iter_rows(min_row=start_row, max_row=end_row_param, min_col=1, max_col=max(question_column, title_column or 1, id_column)):
            question_cell = row[question_column - 1] if question_column <= len(row) else None
            title_cell = row[title_column - 1] if title_column and title_column <= len(row) else None
            id_cell = row[id_column - 1] if id_column <= len(row) else None

            question = str(question_cell.value).strip() if question_cell and question_cell.value else None
            question_id = str(id_cell.value).strip() if id_cell and id_cell.value else None

            # 如果没有指定 title_column，使用问题作为标题
            if title_column and title_cell and title_cell.value:
                title = str(title_cell.value).strip()
            else:
                title = question

            if question:
                questions.append((question, title, question_id))

        wb.close()
        return questions

    def save_results_to_excel(
        self,
        results: BatchQAResult,
        output_path: str,
        template_path: str = None,
    ) -> str:
        """
        将问答结果保存到 Excel

        Args:
            results: 批量问答结果
            output_path: 输出文件路径
            template_path: 模板文件路径（可选，用于保留原始问题数据）

        Returns:
            输出文件路径
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill
        except ImportError:
            raise ImportError("需要安装 openpyxl: pip install openpyxl")

        # 如果提供了模板文件，加载它
        if template_path and Path(template_path).exists():
            wb = openpyxl.load_workbook(template_path)
        else:
            wb = openpyxl.Workbook()

        ws = wb.active
        ws.title = "问答测试结果"

        # 定义样式
        header_font = Font(name='Microsoft YaHei Light', size=8)
        cell_font = Font(name='Microsoft YaHei Light', size=8)
        cell_alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)

        # 设置表头（第 1 行）：编号 | 提问 | 生成回答 | 响应时间 | 引用文档
        headers = ["编号", "提问", "生成回答", "响应时间", "引用文档"]
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.alignment = cell_alignment

        # 填充数据（从第 2 行开始）
        for row_idx, result in enumerate(results.results, 2):
            # 第 1 列：编号
            id_cell = ws.cell(row=row_idx, column=1, value=result.question_id or "")
            id_cell.font = cell_font
            id_cell.alignment = cell_alignment

            # 第 2 列：提问
            question_cell = ws.cell(row=row_idx, column=2, value=result.question)
            question_cell.font = cell_font
            question_cell.alignment = cell_alignment

            # 第 3 列：生成回答
            answer_cell = ws.cell(row=row_idx, column=3, value=result.answer or "")
            answer_cell.font = cell_font
            answer_cell.alignment = cell_alignment

            # 第 4 列：响应时间
            time_cell = ws.cell(row=row_idx, column=4, value=f"{result.response_time:.2f} 秒" if result.response_time else "")
            time_cell.font = cell_font
            time_cell.alignment = cell_alignment

            # 第 5 列：引用文档（从 citations 中提取）
            citations_text = ""
            if result.citations:
                citation_ids = []
                for cite in result.citations:
                    if isinstance(cite, dict):
                        # 使用 doc_id 作为引用文档 ID
                        doc_id = cite.get('doc_id', '')
                        ref_id = cite.get('ref_id', '')
                        if doc_id:
                            # 格式：ref_1:doc_xxx
                            citation_ids.append(f"{ref_id}:{doc_id}" if ref_id else doc_id)
                    elif isinstance(cite, str):
                        citation_ids.append(cite)
                citations_text = "\n".join(citation_ids)

            # 如果 citations_text 为空，尝试从 metadata 中获取
            if not citations_text and result.metadata:
                metadata_citations = result.metadata.get('citations', [])
                if metadata_citations:
                    citation_ids = []
                    for cite in metadata_citations:
                        if isinstance(cite, dict):
                            doc_id = cite.get('doc_id', '')
                            ref_id = cite.get('ref_id', '')
                            if doc_id:
                                citation_ids.append(f"{ref_id}:{doc_id}" if ref_id else doc_id)
                        elif isinstance(cite, str):
                            citation_ids.append(cite)
                    citations_text = "\n".join(citation_ids)

            cite_cell = ws.cell(row=row_idx, column=5, value=citations_text)
            cite_cell.font = cell_font
            cite_cell.alignment = cell_alignment

        # 调整列宽
        ws.column_dimensions['A'].width = 10  # 编号
        ws.column_dimensions['B'].width = 40  # 提问
        ws.column_dimensions['C'].width = 80  # 生成回答
        ws.column_dimensions['D'].width = 15  # 响应时间
        ws.column_dimensions['E'].width = 60  # 引用文档

        # 保存文件（处理中文路径）
        output_path = str(output_path)
        wb.save(output_path)
        wb.close()

        return output_path

    async def run_qa_test_from_config(self, scenario_name: str = "hk_customs") -> BatchQAResult:
        """
        从配置加载测试集并执行问答测试

        Args:
            scenario_name: 测试场景名称

        Returns:
            BatchQAResult 批量问答结果
        """
        # 获取场景配置
        scenario = self.config.get_scenario(scenario_name)
        if not scenario or not scenario.qa_test:
            raise ValueError(f"测试场景 '{scenario_name}' 未找到或未配置 qa_test")

        qa_config = scenario.qa_test

        # 加载问题
        questions = await self.load_questions_from_excel(
            testset_path=qa_config.testset_path,
            question_column=qa_config.question_column,
            start_row=qa_config.start_row,
            end_row=qa_config.end_row,
        )

        # 执行测试
        results = await self.run_batch_qa_tests(
            questions=questions,
            knowledge_base_id=qa_config.knowledge_base_id,
            max_concurrent=qa_config.max_concurrent,
        )

        # 保存结果到 Excel
        output_dir = Path(qa_config.testset_path).parent / "results"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"qa_test_results_{timestamp}.xlsx"

        self.save_results_to_excel(
            results=results,
            output_path=str(output_path),
            template_path=qa_config.testset_path,
        )

        return results
