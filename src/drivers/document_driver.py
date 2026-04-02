"""
文档上传测试驱动器
"""

import asyncio
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..core.config import Config, DocumentUploadConfig
from ..core.auth import AuthManager
from ..core.client import HttpClient


@dataclass
class UploadResult:
    """单个文档上传结果"""
    file_path: str = ""
    file_name: str = ""
    file_size: int = 0
    success: bool = False
    document_id: Optional[str] = None
    job_id: Optional[str] = None
    status: str = ""
    error: Optional[str] = None
    upload_time: float = 0.0
    publish_time: float = 0.0
    total_time: float = 0.0
    vector_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchUploadResult:
    """批量上传结果"""
    total: int = 0
    success: int = 0
    failed: int = 0
    results: List[UploadResult] = field(default_factory=list)
    start_time: datetime = None
    end_time: datetime = None
    file_type_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total == 0:
            return 0.0
        return self.success / self.total

    @property
    def duration(self) -> float:
        """总耗时（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def get_file_type_stats(self) -> Dict[str, Dict[str, int]]:
        """按文件类型统计"""
        stats = {}
        for result in self.results:
            ext = Path(result.file_path).suffix.lower().lstrip(".")
            if ext not in stats:
                stats[ext] = {"total": 0, "success": 0, "failed": 0}
            stats[ext]["total"] += 1
            if result.success:
                stats[ext]["success"] += 1
            else:
                stats[ext]["failed"] += 1
        return stats


class DocumentDriver:
    """文档上传驱动器 - 执行文档上传测试"""

    def __init__(self, config: Config, auth_manager: AuthManager):
        """
        初始化驱动器

        Args:
            config: 配置对象
            auth_manager: 认证管理器
        """
        self.config = config
        self.auth_manager = auth_manager
        self.poll_interval = 2  # 轮询间隔（秒）
        self.poll_timeout = 300  # 超时时间（秒）

    async def upload_document(
        self,
        file_path: str,
        language: str = "zh-cn",
        visibility: str = "private",
    ) -> UploadResult:
        """
        上传单个文档

        Args:
            file_path: 文件路径
            language: 语言
            visibility: 可见性

        Returns:
            UploadResult 上传结果
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return UploadResult(
                file_path=file_path,
                file_name="",
                file_size=0,
                success=False,
                error=f"文件不存在：{file_path}",
            )

        result = UploadResult(
            file_path=file_path,
            file_name=file_path_obj.name,
            file_size=file_path_obj.stat().st_size,
        )

        client = None
        try:
            # 获取认证头
            auth_header = await self.auth_manager.get_auth_header()

            # 步骤 1: 上传文档
            upload_start = time.time()
            client = HttpClient(base_url=self.config.get_base_url("platform_api"))

            endpoint = self.config.get_endpoint("document_upload")

            # 准备文件数据
            with open(file_path, "rb") as f:
                file_content = f.read()

            files = {
                "file": (file_path_obj.name, file_content, "application/octet-stream"),
            }
            data = {
                "doc_name": file_path_obj.name,
                "language": language,
                "visibility": visibility,
            }

            response = await client.post(
                path=endpoint.path,
                headers=auth_header,
                files=files,
                data=data,
            )

            result.upload_time = time.time() - upload_start

            if response.status_code not in (200, 201):
                # 409 Conflict - 检查是否为重复上传
                if response.status_code == 409:
                    data = response.json()
                    error_info = data.get("error", {})
                    details = error_info.get("details", {})
                    # 通过 UPLOAD_DUPLICATE 错误码判断
                    if details.get("code") == "UPLOAD_DUPLICATE":
                        result.document_id = details.get("document_id", "")
                        result.status = "uploaded"
                        result.success = True
                        result.error = None
                        result.metadata = data
                    else:
                        error_msg = error_info.get("message", str(error_info))
                        result.success = False
                        result.error = f"上传冲突：{error_msg}"
                        return result
                else:
                    result.success = False
                    result.error = f"上传失败：{response.status_code} - {response.text}"
                    return result
            else:
                upload_data = response.json()
                result.document_id = upload_data.get("document_id")
                result.status = upload_data.get("status", "")
                result.metadata = upload_data

            # 确保有 document_id
            if not result.document_id:
                result.success = False
                result.error = "未找到 document_id"
                return result

            if result.status != "uploaded":
                result.success = False
                result.error = f"上传状态异常：{result.status}"
                return result

            # 步骤 2: 轮询等待上传完成
            publish_start = time.time()
            publish_success = await self._wait_for_upload_ready(
                document_id=result.document_id,
                auth_header=auth_header,
                client=client,
            )

            if not publish_success:
                result.success = False
                result.error = "等待上传完成超时"
                return result

            # 步骤 3: 发布/解析文档
            publish_result = await self._publish_document(
                document_id=result.document_id,
                auth_header=auth_header,
                client=client,
            )

            result.publish_time = time.time() - publish_start
            result.job_id = publish_result.get("job_id")

            # 步骤 4: 轮询等待发布完成
            publish_success = await self._wait_for_publish_complete(
                document_id=result.document_id,
                auth_header=auth_header,
                client=client,
            )

            result.total_time = time.time() - upload_start
            result.success = publish_success

            if not publish_success:
                result.error = "发布完成等待超时"

            return result

        except Exception as e:
            result.success = False
            result.error = str(e)
            return result

        finally:
            if client:
                await client.close()

    async def _wait_for_upload_ready(
        self,
        document_id: str,
        auth_header: dict,
        client: HttpClient,
    ) -> bool:
        """
        轮询等待上传就绪

        Args:
            document_id: 文档 ID
            auth_header: 认证头
            client: HTTP 客户端

        Returns:
            bool: 是否成功
        """
        endpoint = self.config.get_endpoint("document_status")
        path = endpoint.path.replace("{document_id}", document_id)

        start_time = time.time()
        while time.time() - start_time < self.poll_timeout:
            await asyncio.sleep(self.poll_interval)

            response = await client.get(path=path, headers=auth_header)
            if response.status_code != 200:
                continue

            data = response.json()
            status = data.get("status", "")

            if status == "uploaded":
                return True

        return False

    async def _publish_document(
        self,
        document_id: str,
        auth_header: dict,
        client: HttpClient,
    ) -> dict:
        """
        发布/解析文档

        Args:
            document_id: 文档 ID
            auth_header: 认证头
            client: HTTP 客户端

        Returns:
            发布响应数据
        """
        endpoint = self.config.get_endpoint("document_publish")
        path = endpoint.path.replace("{document_id}", document_id)

        response = await client.post(
            path=path,
            headers=auth_header,
            json={},
        )

        if response.status_code != 200:
            return {"error": f"发布失败：{response.status_code}"}

        return response.json()

    async def _wait_for_publish_complete(
        self,
        document_id: str,
        auth_header: dict,
        client: HttpClient,
    ) -> bool:
        """
        轮询等待发布完成

        Args:
            document_id: 文档 ID
            auth_header: 认证头
            client: HTTP 客户端

        Returns:
            bool: 是否成功
        """
        endpoint = self.config.get_endpoint("document_status")
        path = endpoint.path.replace("{document_id}", document_id)

        start_time = time.time()
        while time.time() - start_time < self.poll_timeout:
            await asyncio.sleep(self.poll_interval)

            response = await client.get(path=path, headers=auth_header)
            if response.status_code != 200:
                continue

            data = response.json()
            status = data.get("status", "")

            if status == "published":
                return True

        return False

    async def batch_upload(
        self,
        upload_config: DocumentUploadConfig,
        max_concurrent: int = None,
    ) -> BatchUploadResult:
        """
        批量上传文档

        Args:
            upload_config: 上传配置
            max_concurrent: 最大并发数

        Returns:
            BatchUploadResult 批量上传结果
        """
        max_concurrent = max_concurrent or upload_config.max_concurrent

        result = BatchUploadResult(
            start_time=datetime.now(),
        )

        # 扫描文件
        base_path = Path(upload_config.base_path)
        if not base_path.exists():
            result.failed = 1
            result.total = 1
            result.end_time = datetime.now()
            result.results.append(
                UploadResult(
                    file_path=str(base_path),
                    file_name="",
                    file_size=0,
                    success=False,
                    error=f"目录不存在：{base_path}",
                )
            )
            return result

        # 收集所有符合条件的文件
        files_to_upload = []
        for ext in upload_config.file_types:
            files_to_upload.extend(base_path.glob(f"**/*.{ext}"))
            files_to_upload.extend(base_path.glob(f"**/*.{ext.upper()}"))

        # 去重
        files_to_upload = list(set(files_to_upload))
        result.total = len(files_to_upload)

        if result.total == 0:
            result.end_time = datetime.now()
            return result

        # 并发控制上传
        semaphore = asyncio.Semaphore(max_concurrent)

        async def upload_with_semaphore(file_path: Path) -> UploadResult:
            async with semaphore:
                return await self.upload_document(
                    file_path=str(file_path),
                    language=upload_config.language,
                    visibility=upload_config.visibility,
                )

        # 执行批量上传
        tasks = [upload_with_semaphore(f) for f in files_to_upload]
        results = await asyncio.gather(*tasks)

        # 统计结果
        result.results = list(results)
        result.success = sum(1 for r in results if r.success)
        result.failed = sum(1 for r in results if not r.success)
        result.file_type_stats = self._get_file_type_stats(results)
        result.end_time = datetime.now()

        return result

    def _get_file_type_stats(
        self,
        results: List[UploadResult],
    ) -> Dict[str, Dict[str, int]]:
        """
        按文件类型统计

        Args:
            results: 上传结果列表

        Returns:
            按文件类型分类的统计字典
        """
        stats = {}
        for result in results:
            ext = Path(result.file_path).suffix.lower().lstrip(".")
            if ext not in stats:
                stats[ext] = {"total": 0, "success": 0, "failed": 0}
            stats[ext]["total"] += 1
            if result.success:
                stats[ext]["success"] += 1
            else:
                stats[ext]["failed"] += 1
        return stats
