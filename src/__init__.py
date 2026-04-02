"""
SensePedia 自动化测试框架
"""

from .core import Config, load_config, AuthManager, HttpClient
from .drivers import DocumentDriver, QADriver, UploadResult, BatchUploadResult, QAResult
from .agents import AutoTestAgent
from .reporters import ReportGenerator

__version__ = "1.0.0"
__all__ = [
    # Config
    "Config",
    "load_config",
    # Auth
    "AuthManager",
    # HTTP
    "HttpClient",
    # Drivers
    "DocumentDriver",
    "QADriver",
    "UploadResult",
    "BatchUploadResult",
    "QAResult",
    # Agent
    "AutoTestAgent",
    # Reporter
    "ReportGenerator",
]
