"""
HTTP 客户端模块
"""

import httpx
from typing import Optional, Dict, Any
from pathlib import Path


class HttpClient:
    """HTTP 客户端 - 处理 API 调用"""

    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 30.0):
        """
        初始化 HTTP 客户端

        Args:
            base_url: 基础 URL
            headers: 默认请求头
            timeout: 超时时间（秒），默认 30 秒
        """
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=timeout,
        )

    async def close(self):
        """关闭客户端"""
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """
        发送 HTTP 请求

        Args:
            method: HTTP 方法
            path: 请求路径
            headers: 请求头
            json: JSON 数据
            data: 表单数据
            files: 上传文件
            params: 查询参数

        Returns:
            httpx.Response 响应对象
        """
        merged_headers = {**self.headers, **(headers or {})}

        response = await self._client.request(
            method=method.upper(),
            url=path,
            headers=merged_headers,
            json=json,
            data=data,
            files=files,
            params=params,
        )

        return response

    async def get(self, path: str, **kwargs) -> httpx.Response:
        """发送 GET 请求"""
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        """发送 POST 请求"""
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs) -> httpx.Response:
        """发送 PUT 请求"""
        return await self.request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs) -> httpx.Response:
        """发送 DELETE 请求"""
        return await self.request("DELETE", path, **kwargs)
