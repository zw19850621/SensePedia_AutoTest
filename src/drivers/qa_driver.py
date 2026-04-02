"""
知识库问答测试驱动器
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..core.config import Config, QATestConfig
from ..core.auth import AuthManager
from ..core.client import HttpClient


@dataclass
class QAResult:
    """单次问答结果"""
    question: str
    success: bool
    answer: Optional[str] = None
    response_time: float = 0.0
    citations: List[dict] = field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


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

    async def ask(
        self,
        query: str,
        knowledge_base_id: str = "",
        top_k: int = 5,
    ) -> QAResult:
        """
        单次问答

        Args:
            query: 问题
            knowledge_base_id: 知识库 ID
            top_k: 返回的顶部结果数

        Returns:
            QAResult 问答结果
        """
        result = QAResult(question=query)

        client = None
        try:
            # 获取认证头
            auth_header = await self.auth_manager.get_auth_header()
            client = HttpClient(base_url=self.config.get_base_url("rag_agent"))

            start_time = time.time()

            endpoint = self.config.get_endpoint("knowledge_qa")
            if endpoint is None:
                # 使用默认配置
                body = {
                    "tool": "rag_query",
                    "action": "rag_query",
                    "params": {
                        "query": query,
                        "knowledge_base_id": knowledge_base_id,
                        "top_k": top_k,
                    },
                }
                path = "/execute"
            else:
                body = self._build_qa_body(query, knowledge_base_id, top_k, endpoint)
                path = endpoint.path

            response = await client.post(
                path=path,
                headers=auth_header,
                json=body,
            )

            result.response_time = time.time() - start_time

            if response.status_code != 200:
                result.success = False
                result.error = f"请求失败：{response.status_code} - {response.text}"
                return result

            data = response.json()

            # 解析响应
            if data.get("status") == "ok" or data.get("status") == "success":
                result.success = True
                result.answer = data.get("answer", "")
                result.citations = data.get("citations", [])
                result.metadata = data
            elif data.get("status") == "no_answer":
                result.success = True  # 无答案也是一种有效结果
                result.answer = ""
                result.metadata = data
            else:
                result.success = False
                result.error = f"响应状态异常：{data.get('status')}"

            return result

        except Exception as e:
            result.success = False
            result.error = str(e)
            return result

        finally:
            if client:
                await client.close()

    def _build_qa_body(
        self,
        query: str,
        knowledge_base_id: str,
        top_k: int,
        endpoint,
    ) -> dict:
        """构建问答请求体"""
        body = {}
        if endpoint.body:
            for key, value in endpoint.body.items():
                if isinstance(value, str):
                    body[key] = value.format(
                        query=query,
                        knowledge_base_id=knowledge_base_id,
                        top_k=top_k,
                    )
                else:
                    body[key] = value
        else:
            body = {
                "tool": "rag_query",
                "action": "rag_query",
                "params": {
                    "query": query,
                    "knowledge_base_id": knowledge_base_id,
                    "top_k": top_k,
                },
            }
        return body

    async def batch_ask(
        self,
        questions: List[str],
        knowledge_base_id: str = "",
        max_concurrent: int = 3,
    ) -> BatchQAResult:
        """
        批量问答

        Args:
            questions: 问题列表
            knowledge_base_id: 知识库 ID
            max_concurrent: 最大并发数

        Returns:
            BatchQAResult 批量问答结果
        """
        result = BatchQAResult(
            start_time=datetime.now(),
        )

        result.total = len(questions)
        if result.total == 0:
            result.end_time = datetime.now()
            return result

        # 并发控制
        semaphore = asyncio.Semaphore(max_concurrent)

        async def ask_with_semaphore(question: str) -> QAResult:
            async with semaphore:
                return await self.ask(
                    query=question,
                    knowledge_base_id=knowledge_base_id,
                )

        # 执行批量问答
        tasks = [ask_with_semaphore(q) for q in questions]
        results = await asyncio.gather(*tasks)

        # 统计结果
        result.results = list(results)
        result.success = sum(1 for r in results if r.success)
        result.failed = sum(1 for r in results if not r.success)
        result.end_time = datetime.now()

        return result

    async def load_questions_from_excel(
        self,
        testset_path: str,
        question_column: int = 2,
    ) -> List[str]:
        """
        从 Excel 文件加载问题列表

        Args:
            testset_path: Excel 文件路径
            question_column: 问题所在列（1-based）

        Returns:
            问题列表
        """
        try:
            import openpyxl
        except ImportError:
            raise ImportError("需要安装 openpyxl: pip install openpyxl")

        wb = openpyxl.load_workbook(testset_path, read_only=True)
        ws = wb.active

        questions = []
        for row in ws.iter_rows(min_row=2, min_col=question_column, max_col=question_column):
            cell = row[0]
            if cell.value and str(cell.value).strip():
                questions.append(str(cell.value).strip())

        wb.close()
        return questions
