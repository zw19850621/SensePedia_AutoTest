"""
测试报告生成器
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from ..drivers.document_driver import BatchUploadResult
from ..drivers.qa_driver import BatchQAResult


class ReportGenerator:
    """报告生成器 - 生成测试报告"""

    def __init__(self, output_dir: str = None):
        """
        初始化报告生成器

        Args:
            output_dir: 报告输出目录，默认为 ./reports
        """
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / "reports"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_upload_report(
        self,
        result: BatchUploadResult,
        scenario_name: str = "",
    ) -> str:
        """
        生成文档上传报告

        Args:
            result: 批量上传结果
            scenario_name: 场景名称

        Returns:
            Markdown 格式报告
        """
        lines = []

        # 标题
        lines.append("# 文档上传测试报告")
        lines.append("")
        lines.append(f"**场景**: {scenario_name or '未命名'}")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 总体统计
        lines.append("## 总体统计")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 总文件数 | {result.total} |")
        lines.append(f"| 成功上传 | {result.success} ({result.success_rate:.1%}) |")
        lines.append(f"| 失败文件 | {result.failed} |")
        lines.append(f"| 总耗时 | {result.duration:.1f} 秒 |")
        lines.append(f"| 平均每个文件耗时 | {result.duration / result.total:.1f} 秒 |" if result.total > 0 else "| 平均每个文件耗时 | N/A |")
        lines.append("")

        # 按文件类型统计
        file_type_stats = result.get_file_type_stats()
        if file_type_stats:
            lines.append("## 按文件类型统计")
            lines.append("")
            lines.append("| 文件类型 | 总数 | 成功 | 失败 | 成功率 |")
            lines.append("|----------|------|------|------|--------|")
            for ext, stats in sorted(file_type_stats.items()):
                success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
                lines.append(
                    f"| {ext.upper()} | {stats['total']} | {stats['success']} | "
                    f"{stats['failed']} | {success_rate:.1%} |"
                )
            lines.append("")

        # 失败详情
        failed_results = [r for r in result.results if not r.success]
        if failed_results:
            lines.append("## 失败详情")
            lines.append("")
            lines.append("| 文件名 | 错误原因 |")
            lines.append("|--------|----------|")
            for r in failed_results:
                error_msg = r.error[:100] + "..." if len(r.error) > 100 else r.error
                lines.append(f"| {Path(r.file_path).name} | {error_msg} |")
            lines.append("")

        # 成功文件列表
        success_results = [r for r in result.results if r.success]
        if success_results:
            lines.append("## 成功文件列表")
            lines.append("")
            lines.append("| 文件名 | 大小 | 文档 ID | 上传耗时 | 发布耗时 | 总耗时 |")
            lines.append("|--------|------|--------|----------|----------|--------|")
            for r in success_results[:50]:  # 最多显示 50 个
                size_kb = r.file_size / 1024
                lines.append(
                    f"| {Path(r.file_path).name} | {size_kb:.1f} KB | "
                    f"{r.document_id[:20] if r.document_id else 'N/A'}... | "
                    f"{r.upload_time:.1f}s | {r.publish_time:.1f}s | {r.total_time:.1f}s |"
                )
            if len(success_results) > 50:
                lines.append(f"*... 还有 {len(success_results) - 50} 个文件*")
            lines.append("")

        return "\n".join(lines)

    def generate_qa_report(
        self,
        result: BatchQAResult,
        scenario_name: str = "",
    ) -> str:
        """
        生成问答测试报告

        Args:
            result: 批量问答结果
            scenario_name: 场景名称

        Returns:
            Markdown 格式报告
        """
        lines = []

        # 标题
        lines.append("# 知识库问答测试报告")
        lines.append("")
        lines.append(f"**场景**: {scenario_name or '未命名'}")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 总体统计
        lines.append("## 总体统计")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 总问题数 | {result.total} |")
        lines.append(f"| 成功回答 | {result.success} ({result.success_rate:.1%}) |")
        lines.append(f"| 失败问题 | {result.failed} |")
        lines.append(f"| 总耗时 | {result.duration:.1f} 秒 |")
        lines.append("")

        # 响应时间统计
        lines.append("## 响应时间统计")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 平均响应时间 | {result.avg_response_time:.2f} 秒 |")
        lines.append(f"| P95 响应时间 | {result.p95_response_time:.2f} 秒 |")
        lines.append(f"| P99 响应时间 | {result.p99_response_time:.2f} 秒 |")
        lines.append("")

        # 失败详情
        failed_results = [r for r in result.results if not r.success]
        if failed_results:
            lines.append("## 失败详情")
            lines.append("")
            lines.append("| 问题 | 错误原因 |")
            lines.append("|------|----------|")
            for r in failed_results:
                question = r.question[:50] + "..." if len(r.question) > 50 else r.question
                error_msg = r.error[:100] + "..." if len(r.error) > 100 else r.error
                lines.append(f"| {question} | {error_msg} |")
            lines.append("")

        # 成功回答列表
        success_results = [r for r in result.results if r.success]
        if success_results:
            lines.append("## 请求详情")
            lines.append("")
            for i, r in enumerate(success_results[:20], 1):  # 最多显示 20 个
                lines.append(f"### Q{i} ###")
                lines.append("")
                lines.append(f"**响应时间**: {r.response_time:.2f} 秒")
                lines.append("")
                lines.append("**提问请求**: ")

                # 从 request_details 中找到 streaming_query 请求
                streaming_req = None
                for req in r.request_details:
                    if req.get('api') == 'streaming_query':
                        streaming_req = req
                        break

                if streaming_req:
                    # 显示请求 URL
                    base_url = "http://10.210.0.61:8022"
                    path = streaming_req.get('path', '/v1/rag/query/stream')
                    lines.append(f"{streaming_req.get('method', 'POST')} {base_url}{path}")
                    lines.append("")
                    lines.append("**请求体:**")
                    lines.append(json.dumps(streaming_req.get('request_body', {}), ensure_ascii=False, indent=2))
                    lines.append("")
                    lines.append("**响应体:**")
                    # 从 response_data 中提取原始流式响应（raw 字段）
                    response_data = streaming_req.get('response_data', {})
                    raw_response = response_data.get('raw', '')
                    if raw_response:
                        lines.append(raw_response)
                    else:
                        answer_text = r.answer if r.answer else "(无答案)"
                        lines.append(answer_text)
                else:
                    lines.append("(未找到请求详情)")

                lines.append("")
                lines.append("---")
                lines.append("")

            if len(success_results) > 20:
                lines.append(f"*... 还有 {len(success_results) - 20} 个请求详情未显示*")
                lines.append("")

        return "\n".join(lines)

    def generate_full_report(
        self,
        upload_result: Optional[BatchUploadResult] = None,
        qa_result: Optional[BatchQAResult] = None,
        scenario_name: str = "",
    ) -> str:
        """
        生成完整测试报告

        Args:
            upload_result: 上传结果
            qa_result: 问答结果
            scenario_name: 场景名称

        Returns:
            Markdown 格式完整报告
        """
        lines = []

        # 总标题
        lines.append("# SensePedia 自动化测试报告")
        lines.append("")
        lines.append(f"**场景**: {scenario_name or '未命名'}")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 文档上传报告
        if upload_result:
            lines.append(self.generate_upload_report(upload_result, scenario_name))
            lines.append("")
            lines.append("---")
            lines.append("")

        # 问答测试报告
        if qa_result:
            lines.append(self.generate_qa_report(qa_result, scenario_name))
            lines.append("")

        return "\n".join(lines)

    def save_report(
        self,
        content: str,
        filename: str = None,
        scenario_name: str = "",
    ) -> str:
        """
        保存报告到文件

        Args:
            content: 报告内容
            filename: 文件名，默认使用时间戳
            scenario_name: 场景名称（用于生成目录）

        Returns:
            保存的文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            filename = f"{timestamp}.md"

        # 如果指定了场景名称，创建子目录
        if scenario_name:
            scenario_dir = self.output_dir / scenario_name
            scenario_dir.mkdir(parents=True, exist_ok=True)
            file_path = scenario_dir / filename
        else:
            file_path = self.output_dir / filename

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return str(file_path)
