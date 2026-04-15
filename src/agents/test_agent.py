"""
AutoTest Agent - 自然语言驱动的测试执行引擎
"""

import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..core.config import Config, load_config
from ..core.auth import AuthManager
from ..drivers.document_driver import DocumentDriver, BatchUploadResult
from ..drivers.qa_driver import QADriver, BatchQAResult
from ..reporters.report_generator import ReportGenerator

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class TestIntent:
    """测试意图"""
    action: str = "test"  # test, upload, qa
    scenario: Optional[str] = None
    target: Optional[str] = None
    raw_command: str = ""


@dataclass
class TestExecutionResult:
    """测试执行结果"""
    success: bool = False
    intent: TestIntent = None
    upload_result: Optional[BatchUploadResult] = None
    qa_result: Optional[BatchQAResult] = None
    report_path: Optional[str] = None
    error: Optional[str] = None
    message: str = ""


class AutoTestAgent:
    """AutoTest Agent - 自然语言驱动的测试执行引擎"""

    def __init__(self, config: Config = None):
        """
        初始化 Agent

        Args:
            config: 配置对象，默认为 None 时自动加载
        """
        self.config = config or load_config()
        self.auth_manager = AuthManager(self.config)
        self.report_generator = ReportGenerator.from_config(self.config)
        self._document_driver: Optional[DocumentDriver] = None
        self._qa_driver: Optional[QADriver] = None

    @property
    def document_driver(self) -> DocumentDriver:
        """获取文档上传驱动器"""
        if self._document_driver is None:
            self._document_driver = DocumentDriver(self.config, self.auth_manager)
        return self._document_driver

    @property
    def qa_driver(self) -> QADriver:
        """获取问答测试驱动器"""
        if self._qa_driver is None:
            self._qa_driver = QADriver(self.config, self.auth_manager)
        return self._qa_driver

    def _parse_intent(self, command: str) -> TestIntent:
        """
        解析自然语言命令意图

        Args:
            command: 自然语言命令

        Returns:
            TestIntent 意图对象
        """
        command = command.strip().lower()
        intent = TestIntent(raw_command=command)

        # 识别动作 - 注意顺序：先检查特定动作，再检查通用动作
        # 1. 先检查"问答"（因为"问答测试"应该是 QA 而不是完整测试）
        if any(word in command for word in ["问答", "qa", "提问", "question", "回答", "answer"]):
            intent.action = "qa"
        # 2. 再检查"上传"
        elif any(word in command for word in ["上传", "upload", "导入", "import"]):
            intent.action = "upload"
        # 3. 最后检查"测试"（通用动作）
        elif any(word in command for word in ["测试", "test", "运行", "run", "执行", "execute"]):
            intent.action = "test"
        else:
            intent.action = "test"  # 默认为测试

        # 识别场景名称
        # 匹配中文场景名（如"香港海关知识库"、"海关测试"）
        scenario_patterns = [
            r"(?:帮我 | 给我 | 进行 | 做)?(?:测试 | 运行 | 执行)?(.+?)(?:知识库 | 测试 | 场景)?",
            r"(?:test|run|execute)?\s*(.+?)\s*(?:knowledge|base|scenario)?",
        ]

        # 从配置中获取所有场景名称进行匹配
        for scenario_name in self.config.scenarios.keys():
            if scenario_name in command or scenario_name.lower() in command:
                intent.scenario = scenario_name
                return intent

        # 尝试从中文提取场景关键词
        zh_keywords = ["香港", "海关", " demo", "演示", "测试"]
        for keyword in zh_keywords:
            if keyword in command:
                # 根据关键词推断场景
                if "香港" in command and "海关" in command:
                    intent.scenario = "hk_customs"
                elif "demo" in command or "演示" in command:
                    intent.scenario = "demo"
                break

        # 如果没有匹配到场景，使用第一个启用的场景
        if not intent.scenario:
            for name, scenario in self.config.scenarios.items():
                if scenario.get("enabled", True):
                    intent.scenario = name
                    break

        return intent

    def _match_scenario(self, intent: TestIntent) -> Optional[Dict[str, Any]]:
        """
        匹配场景配置

        Args:
            intent: 意图对象

        Returns:
            场景配置字典
        """
        if not intent.scenario:
            return None

        scenario_config = self.config.get_scenario(intent.scenario)
        if not scenario_config:
            return None

        return self.config.scenarios.get(intent.scenario, {})

    async def execute(self, command: str) -> TestExecutionResult:
        """
        执行自然语言命令

        Args:
            command: 自然语言命令，如"帮我测试香港海关知识库"

        Returns:
            TestExecutionResult 执行结果
        """
        # 1. 解析意图
        intent = self._parse_intent(command)
        result = TestExecutionResult(intent=intent)

        # 2. 匹配场景
        scenario_config = self._match_scenario(intent)
        if not scenario_config:
            result.success = False
            result.error = f"未找到场景配置：{intent.scenario}"
            result.message = f"未找到场景 '{intent.scenario}' 的配置，请检查 config/scenarios.yaml"
            return result

        scenario = self.config.get_scenario(intent.scenario)
        if not scenario.enabled:
            result.success = False
            result.error = f"场景未启用：{intent.scenario}"
            result.message = f"场景 '{scenario.name}' 未启用，请在 config/scenarios.yaml 中设置 enabled: true"
            return result

        result.message = f"开始执行测试场景：{scenario.name}"

        try:
            # 3. 根据意图执行测试
            if intent.action == "upload":
                # 仅执行文档上传
                result.upload_result = await self._run_upload(scenario)
            elif intent.action == "qa":
                # 仅执行问答测试
                result.qa_result = await self._run_qa(scenario)
            else:
                # 执行完整测试（上传 + 问答）
                result.upload_result = await self._run_upload(scenario)
                result.qa_result = await self._run_qa(scenario)

            # 4. 生成报告
            report_content = self.report_generator.generate_full_report(
                upload_result=result.upload_result,
                qa_result=result.qa_result,
                scenario_name=intent.scenario,
            )
            result.report_path = self.report_generator.save_report(
                report_content,
                scenario_name=intent.scenario,
            )

            # 5. 保存 Excel 结果（如果有 QA 测试）
            if result.qa_result:
<<<<<<< HEAD
                excel_path = await self._save_qa_result_to_excel(result.qa_result, intent.scenario)
=======
                excel_path = self._save_qa_result_to_excel(result.qa_result, intent.scenario)
>>>>>>> 49908992903b80666c2c2410b1ef2e5b63497299
                result.message = f"测试执行完成，报告已保存至：{result.report_path}，Excel 结果已保存至：{excel_path}"
            else:
                result.message = f"测试执行完成，报告已保存至：{result.report_path}"

            result.success = True

        except Exception as e:
            result.success = False
            result.error = str(e)
            result.message = f"测试执行失败：{str(e)}"

        return result

    async def _run_upload(self, scenario) -> Optional[BatchUploadResult]:
        """
        执行文档上传测试

        Args:
            scenario: 场景配置

        Returns:
            BatchUploadResult 上传结果
        """
        upload_config = scenario.document_upload
        if not upload_config:
            return None

        base_path = Path(upload_config.base_path)
        if not base_path.exists():
            raise Exception(f"文档目录不存在：{base_path}")

        # 执行批量上传
        result = await self.document_driver.batch_upload(upload_config)
        return result

    async def _run_qa(self, scenario) -> Optional[BatchQAResult]:
        """
        执行问答测试

        Args:
            scenario: 场景配置

        Returns:
            BatchQAResult 问答结果
        """
        logger.info("=" * 60)
        logger.info(f"开始执行问答测试场景：{scenario.name}")

        qa_config = scenario.qa_test
        if not qa_config:
            logger.warning(f"场景 {scenario.name} 未配置 qa_test")
            return None

        logger.info(f"测试集路径：{qa_config.testset_path}")
        logger.info(f"工作表：{qa_config.sheet_name or '默认（第一个）'}, 问题列：{qa_config.question_column}, 起始行：{qa_config.start_row}")

        # 从 Excel 加载问题（使用问题文本作为标题）
        questions = await self.qa_driver.load_questions_from_excel(
            testset_path=qa_config.testset_path,
            sheet_name=qa_config.sheet_name,
            question_column=qa_config.question_column,
            id_column=qa_config.id_column or 1,  # 从第一列读取编号
            start_row=qa_config.start_row,
            end_row=qa_config.end_row,
        )

        if not questions:
            raise Exception(f"测试集中没有找到问题：{qa_config.testset_path}")

        logger.info(f"加载问题数量：{len(questions)}")

        # 执行批量问答
        result = await self.qa_driver.run_batch_qa_tests(
            questions=questions,
            knowledge_base_id=qa_config.knowledge_base_id,
            max_concurrent=qa_config.max_concurrent,
        )

        return result

<<<<<<< HEAD
    async def _save_qa_result_to_excel(self, qa_result, scenario_name: str) -> str:
=======
    def _save_qa_result_to_excel(self, qa_result, scenario_name: str) -> str:
>>>>>>> 49908992903b80666c2c2410b1ef2e5b63497299
        """
        保存 QA 测试结果到 Excel 文件

        Args:
            qa_result: 批量问答结果
            scenario_name: 场景名称

        Returns:
            保存的文件路径
        """
        # 使用与报告相同的输出目录
        excel_dir = self.report_generator.output_dir / scenario_name
        excel_dir.mkdir(parents=True, exist_ok=True)

        # 使用与报告相同的时间戳
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        excel_filename = f"{timestamp}.xlsx"
        excel_path = excel_dir / excel_filename

        # 保存 Excel
<<<<<<< HEAD
        await self.qa_driver.save_results_to_excel(qa_result, str(excel_path))
=======
        self.qa_driver.save_results_to_excel(qa_result, str(excel_path))
>>>>>>> 49908992903b80666c2c2410b1ef2e5b63497299

        return str(excel_path)

    async def upload_documents(
        self,
        scenario_name: str = None,
        base_path: str = None,
        file_types: List[str] = None,
    ) -> BatchUploadResult:
        """
        直接执行文档上传

        Args:
            scenario_name: 场景名称（从配置加载）
            base_path: 文档目录路径（直接指定）
            file_types: 文件类型列表

        Returns:
            BatchUploadResult 上传结果
        """
        if scenario_name:
            scenario = self.config.get_scenario(scenario_name)
            if scenario and scenario.document_upload:
                return await self.document_driver.batch_upload(scenario.document_upload)

        # 使用默认配置
        from ..core.config import DocumentUploadConfig
        config = DocumentUploadConfig(
            base_path=base_path or "./data/documents",
            file_types=file_types or ["pdf", "docx", "md", "txt"],
        )
        return await self.document_driver.batch_upload(config)

    async def run_qa_tests(
        self,
        scenario_name: str = None,
        testset_path: str = None,
        questions: List[tuple] = None,  # [(question, title), ...]
    ) -> BatchQAResult:
        """
        直接执行问答测试

        Args:
            scenario_name: 场景名称（从配置加载）
            testset_path: 测试集路径（直接指定）
            questions: 问题列表（直接指定），每个元素为 (问题，标题) 元组

        Returns:
            BatchQAResult 问答结果
        """
        if scenario_name:
            scenario = self.config.get_scenario(scenario_name)
            if scenario and scenario.qa_test:
                qa_config = scenario.qa_test
                questions = await self.qa_driver.load_questions_from_excel(
                    testset_path=qa_config.testset_path,
                    question_column=qa_config.question_column,
                    title_column=1,
                    start_row=qa_config.start_row,
                    end_row=qa_config.end_row,
                )
                return await self.qa_driver.run_batch_qa_tests(
                    questions=questions,
                    knowledge_base_id=qa_config.knowledge_base_id,
                    max_concurrent=qa_config.max_concurrent,
                )

        # 使用默认配置
        if questions:
            return await self.qa_driver.run_batch_qa_tests(questions)
        elif testset_path:
            questions = await self.qa_driver.load_questions_from_excel(testset_path)
            return await self.qa_driver.run_batch_qa_tests(questions)
        else:
            raise ValueError("需要指定 scenario_name、testset_path 或 questions")
