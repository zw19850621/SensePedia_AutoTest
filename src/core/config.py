"""
配置加载和管理模块
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AuthConfig:
    """认证配置"""
    username: str = "admin"
    password: str = "changeme"
    login_endpoint: str = "auth_login"
    refresh_threshold: int = 300


@dataclass
class EndpointConfig:
    """API 端点配置"""
    method: str
    path: str
    base: str = "platform_api"
    content_type: str = "application/json"
    body: dict = field(default_factory=dict)
    fields: list = field(default_factory=list)
    response: dict = field(default_factory=dict)


@dataclass
class DocumentUploadConfig:
    """文档上传配置"""
    base_path: str
    file_types: list = field(default_factory=lambda: ["pdf", "docx", "md", "txt"])
    language: str = "zh-cn"
    visibility: str = "private"
    max_concurrent: int = 3


@dataclass
class QATestConfig:
    """问答测试配置"""
    testset_path: str
    question_column: int = 2
    expected_answer_column: Optional[int] = None
    knowledge_base_id: str = ""
    max_concurrent: int = 3


@dataclass
class ScenarioConfig:
    """测试场景配置"""
    name: str
    description: str = ""
    enabled: bool = True
    document_upload: Optional[DocumentUploadConfig] = None
    qa_test: Optional[QATestConfig] = None


@dataclass
class Config:
    """主配置类"""
    base_urls: dict = field(default_factory=dict)
    endpoints: dict = field(default_factory=dict)
    auth: AuthConfig = field(default_factory=AuthConfig)
    scenarios: dict = field(default_factory=dict)
    rules: dict = field(default_factory=dict)

    def get_endpoint(self, name: str) -> Optional[EndpointConfig]:
        """获取指定名称的端点配置"""
        if name not in self.endpoints:
            return None
        data = self.endpoints[name]
        return EndpointConfig(
            method=data.get("method", "GET"),
            path=data.get("path", ""),
            base=data.get("base", "platform_api"),
            content_type=data.get("content_type", "application/json"),
            body=data.get("body", {}),
            fields=data.get("fields", []),
            response=data.get("response", {}),
        )

    def get_base_url(self, base_name: str) -> str:
        """获取基础 URL"""
        return self.base_urls.get(base_name, "")

    def get_scenario(self, name: str) -> Optional[ScenarioConfig]:
        """获取指定名称的场景配置"""
        if name not in self.scenarios:
            return None
        data = self.scenarios[name]
        return ScenarioConfig(
            name=data.get("name", name),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            document_upload=self._parse_upload_config(data.get("document_upload", {})),
            qa_test=self._parse_qa_config(data.get("qa_test", {})),
        )

    def _parse_upload_config(self, data: dict) -> Optional[DocumentUploadConfig]:
        """解析文档上传配置"""
        if not data or not data.get("enabled", True):
            return None
        return DocumentUploadConfig(
            base_path=data.get("base_path", "./data/documents"),
            file_types=data.get("file_types", ["pdf", "docx", "md", "txt"]),
            language=data.get("language", "zh-cn"),
            visibility=data.get("visibility", "private"),
            max_concurrent=data.get("max_concurrent", 3),
        )

    def _parse_qa_config(self, data: dict) -> Optional[QATestConfig]:
        """解析问答测试配置"""
        if not data or not data.get("enabled", True):
            return None
        return QATestConfig(
            testset_path=data.get("testset_path", ""),
            question_column=data.get("question_column", 2),
            expected_answer_column=data.get("expected_answer_column"),
            knowledge_base_id=data.get("knowledge_base_id", ""),
            max_concurrent=data.get("max_concurrent", 3),
        )


def load_config(config_dir: str = None) -> Config:
    """
    加载配置文件

    Args:
        config_dir: 配置文件目录，默认为 ./config

    Returns:
        Config 配置对象
    """
    if config_dir is None:
        config_dir = Path(__file__).parent.parent.parent / "config"
    else:
        config_dir = Path(config_dir)

    config = Config()

    # 加载端点配置
    endpoints_path = config_dir / "endpoints.yaml"
    if endpoints_path.exists():
        with open(endpoints_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            config.base_urls = data.get("base_urls", {})
            config.endpoints = data.get("endpoints", {})

    # 加载认证配置
    auth_path = config_dir / "auth.yaml"
    if auth_path.exists():
        with open(auth_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            auth_data = data.get("auth", {})
            config.auth = AuthConfig(
                username=auth_data.get("credentials", {}).get("username", "admin"),
                password=auth_data.get("credentials", {}).get("password", "changeme"),
                login_endpoint=auth_data.get("login_endpoint", "auth_login"),
                refresh_threshold=auth_data.get("token", {}).get("refresh_threshold", 300),
            )

    # 加载场景配置
    scenarios_path = config_dir / "scenarios.yaml"
    if scenarios_path.exists():
        with open(scenarios_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            config.scenarios = data.get("scenarios", {})

    # 加载规则配置
    rules_path = config_dir / "rules.yaml"
    if rules_path.exists():
        with open(rules_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            config.rules = data.get("rules", {})

    return config
