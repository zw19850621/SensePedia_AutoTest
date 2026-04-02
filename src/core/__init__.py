"""
SensePedia 自动化测试框架 - 核心包
"""

from .config import Config, load_config
from .client import HttpClient
from .auth import AuthManager

__all__ = ["Config", "load_config", "HttpClient", "AuthManager"]
