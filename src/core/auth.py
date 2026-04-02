"""
认证管理模块
"""

import time
from typing import Optional
from dataclasses import dataclass

from .client import HttpClient
from .config import AuthConfig, Config


@dataclass
class TokenInfo:
    """Token 信息"""
    token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    user: dict = None
    acquired_at: float = None

    def is_expired(self, threshold: int = 300) -> bool:
        """
        检查 token 是否即将过期

        Args:
            threshold: 过期阈值（秒）

        Returns:
            bool: 是否即将过期
        """
        if self.acquired_at is None:
            return True
        elapsed = time.time() - self.acquired_at
        return elapsed >= (self.expires_in - threshold)


class AuthManager:
    """认证管理器 - 处理登录、token 获取和刷新"""

    def __init__(self, config: Config):
        """
        初始化认证管理器

        Args:
            config: 配置对象
        """
        self.config = config
        self.auth_config = config.auth
        self._token: Optional[TokenInfo] = None
        self._client: Optional[HttpClient] = None

    def _get_client(self) -> HttpClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            base_url = self.config.get_base_url("platform_api")
            self._client = HttpClient(base_url=base_url)
        return self._client

    async def login(self, username: str = None, password: str = None) -> str:
        """
        登录获取 JWT token

        Args:
            username: 用户名，默认为配置中的值
            password: 密码，默认为配置中的值

        Returns:
            JWT token 字符串
        """
        username = username or self.auth_config.username
        password = password or self.auth_config.password

        endpoint = self.config.get_endpoint("auth_login")
        client = HttpClient(base_url=self.config.get_base_url("platform_api"))

        try:
            # 构建请求体
            body = {}
            for key, value in endpoint.body.items():
                # 替换占位符
                body[key] = value.format(username=username, password=password)

            response = await client.post(
                path=endpoint.path,
                json=body,
            )

            if response.status_code != 200:
                raise Exception(f"登录失败：{response.status_code} - {response.text}")

            data = response.json()
            token_field = endpoint.response.get("token_field", "token")
            token = data.get(token_field)

            if not token:
                raise Exception(f"登录响应中未找到 token 字段：{token_field}")

            # 保存 token 信息
            self._token = TokenInfo(
                token=token,
                token_type=data.get("token_type", "bearer"),
                expires_in=data.get("expires_in", 86400),
                user=data.get("user"),
                acquired_at=time.time(),
            )

            return token

        finally:
            await client.close()

    async def get_valid_token(self) -> str:
        """
        获取有效 token（自动刷新）

        Returns:
            有效的 JWT token
        """
        if self._token is None or self._token.is_expired(self.auth_config.refresh_threshold):
            return await self.login()
        return self._token.token

    async def get_auth_header(self) -> dict:
        """
        获取认证请求头

        Returns:
            包含 Authorization 的字典
        """
        token = await self.get_valid_token()
        token_type = self._token.token_type if self._token else "bearer"
        return {"Authorization": f"{token_type.title()} {token}"}

    def get_current_user(self) -> Optional[dict]:
        """
        获取当前登录用户信息

        Returns:
            用户信息字典
        """
        return self._token.user if self._token else None
