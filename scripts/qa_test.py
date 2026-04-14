#!/usr/bin/env python
"""
知识库问答测试脚本

用法:
    python scripts/qa_test.py
    python scripts/qa_test.py --scenario hk_customs
    python scripts/qa_test.py --testset "D:/tests/questions.xlsx"
    python scripts/qa_test.py --testset "D:/tests/questions.xlsx" --concurrency 5
"""

import asyncio
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import load_config
from src.core.auth import AuthManager
from src.drivers.qa_driver import QADriver

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(
        description="知识库问答测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 直接运行（交互式选择模式 + 使用第一个启用的场景）
  python scripts/qa_test.py

  # 指定场景
  python scripts/qa_test.py --scenario hk_customs

  # 直接指定测试集
  python scripts/qa_test.py --testset "D:/tests/questions.xlsx"
        """
    )

    parser.add_argument(
        "--scenario",
        type=str,
        help="测试场景名称"
    )
    parser.add_argument(
        "--testset",
        type=str,
        help="测试集 Excel 文件路径"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=0,
        help="最大并发数（默认使用配置值）"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="结果输出目录"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件目录"
    )
    parser.add_argument(
        "--start-row",
        type=int,
        help="起始行号"
    )
    parser.add_argument(
        "--end-row",
        type=int,
        help="结束行号"
    )

    args = parser.parse_args()

    # 加载配置
    config_path = args.config if args.config else None
    config = load_config(config_path)

    # 交互式选择模式
    print("\n请选择运行模式：")
    print("  1 - Fixed Pipeline (固定流水线)")
    print("  2 - Flexible Skills (灵活技能)")
    current_mode = config.endpoints.get("rag_create_message", {}).get("body", {}).get("chat_mode", "flex")
    default_hint = "1" if current_mode == "pipeline" else "2"
    choice = input(f"\n请输入选项 (回车使用配置默认 [{default_hint}]): ").strip()

    if choice == "1":
        config.endpoints.setdefault("rag_create_message", {}).setdefault("body", {})["chat_mode"] = "pipeline"
        print("已选择：Fixed Pipeline (pipeline)\n")
    elif choice == "2":
        config.endpoints.setdefault("rag_create_message", {}).setdefault("body", {})["chat_mode"] = "flex"
        print("已选择：Flexible Skills (flex)\n")
    elif choice == "":
        # 回车使用配置默认值
        if current_mode == "pipeline":
            print(f"使用配置默认：Fixed Pipeline (pipeline)\n")
        else:
            print(f"使用配置默认：Flexible Skills (flex)\n")
    else:
        print(f"无效选项 '{choice}'，使用配置默认\n")

    # 初始化认证管理器
    auth_manager = AuthManager(config)
    await auth_manager.login()

    # 初始化驱动器
    driver = QADriver(config, auth_manager)

    # 确定使用哪个场景或测试集
    results = None
    output_dir = None
    template_path = None

    if args.scenario:
        # 指定场景
        scenario_name = args.scenario
    else:
        # 使用第一个启用的场景
        scenario_name = None
        for name, data in config.scenarios.items():
            if data.get("enabled", True) and data.get("qa_test", {}).get("enabled", True):
                scenario_name = name
                break

    if scenario_name:
        scenario = config.get_scenario(scenario_name)
        if not scenario or not scenario.qa_test:
            print(f"错误：场景 '{scenario_name}' 未找到或未配置 qa_test")
            sys.exit(1)

        qa_config = scenario.qa_test
        concurrency = args.concurrency if args.concurrency > 0 else qa_config.max_concurrent
        output_dir = Path(qa_config.testset_path).parent / "results"
        template_path = qa_config.testset_path

        print(f"\n{'='*60}")
        print(f"执行问答测试 - 场景：{scenario_name}")
        print(f"{'='*60}")
        print(f"测试集：{qa_config.testset_path}")
        print(f"并发数：{concurrency}")
        print(f"{'='*60}\n")

        # 加载问题
        questions = await driver.load_questions_from_excel(
            testset_path=qa_config.testset_path,
            question_column=qa_config.question_column,
            start_row=qa_config.start_row or 2,
            end_row=qa_config.end_row if args.end_row is None else args.end_row,
        )

        # 执行测试（driver 内部处理中断，不会抛出异常）
        results = await driver.run_batch_qa_tests(
            questions=questions,
            knowledge_base_id=qa_config.knowledge_base_id,
            max_concurrent=concurrency,
        )
    elif args.testset:
        # 直接指定测试集
        testset_path = Path(args.testset)
        if not testset_path.exists():
            print(f"错误：测试集不存在：{testset_path}")
            sys.exit(1)

        concurrency = args.concurrency if args.concurrency > 0 else 3
        output_dir = Path(args.output) if args.output else testset_path.parent / "results"
        template_path = str(testset_path)

        print(f"\n{'='*60}")
        print(f"执行问答测试")
        print(f"{'='*60}")
        print(f"测试集：{testset_path}")
        print(f"并发数：{concurrency}")
        print(f"{'='*60}\n")

        # 加载问题
        questions = await driver.load_questions_from_excel(
            testset_path=str(testset_path),
            question_column=2,
            start_row=args.start_row or 2,
            end_row=args.end_row,
        )

        # 执行测试
        results = await driver.run_batch_qa_tests(
            questions=questions,
            knowledge_base_id="ALL_KB",
            max_concurrent=concurrency,
        )
    else:
        print("错误：未找到可用的场景配置，也未指定 --testset")
        print("请在 config/scenarios.yaml 中配置场景，或使用 --scenario 指定场景")
        sys.exit(1)

    # 保存结果（driver 已处理中断，results 一定会有值）
    if results and results.results:
        if args.output:
            output_dir = Path(args.output)
        if output_dir is None:
            output_dir = Path("results")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chat_mode_name = driver._get_chat_mode_header()
        suffix = "_interrupted" if len(results.results) < results.total else ""
        output_path = output_dir / f"{chat_mode_name}_{timestamp}{suffix}.xlsx"

        # 兜底：即使正常保存失败，也尝试用最简单的方式保存结果
        try:
            await driver.save_results_to_excel(
                results=results,
                output_path=str(output_path),
                template_path=template_path,
            )
        except Exception as e:
            logger.error(f"保存结果文件失败：{e}，尝试使用简化模式保存...")
            fallback_path = output_dir / f"{chat_mode_name}_{timestamp}_fallback.xlsx"
            try:
                await driver.save_results_to_excel(
                    results=results,
                    output_path=str(fallback_path),
                    template_path=None,  # 不使用模板
                )
                output_path = fallback_path
                print(f"⚠ 正常保存失败，已使用简化模式保存至：{output_path}")
            except Exception as e2:
                logger.error(f"简化模式保存也失败：{e2}")

        # 输出结果摘要
        all_completed = len(results.results) >= results.total
        print(f"\n{'='*60}")
        if not all_completed:
            print(f"测试被中断 - 已保存部分结果")
        else:
            print(f"测试完成")
        print(f"{'='*60}")
        print(f"总数：{results.total} | 已完成：{len(results.results)} | 成功：{results.success} | 失败：{results.failed}")
        if len(results.results) > 0:
            print(f"成功率：{results.success_rate:.1%}")
            print(f"平均响应时间：{results.avg_response_time:.2f}s")
            print(f"P95 响应时间：{results.p95_response_time:.2f}s")
        print(f"总耗时：{results.duration:.2f}s")
        print(f"\n结果已保存至：{output_path}")
        print(f"{'='*60}\n")

        sys.exit(0 if results.success == results.total else 1)
    else:
        print("\n没有已完成的测试结果")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
