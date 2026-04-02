"""
SensePedia 自动化测试框架 - 主入口
"""

import asyncio
import sys
import argparse

from src.agents import AutoTestAgent
from src.core import load_config


async def main_async():
    """异步主入口"""
    parser = argparse.ArgumentParser(
        description="SensePedia 自动化测试框架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用自然语言命令
  python main.py "帮我测试香港海关知识库"

  # 仅执行文档上传
  python main.py --upload --scenario hk_customs

  # 仅执行问答测试
  python main.py --qa --scenario hk_customs

  # 直接指定文档目录上传
  python main.py --upload --path "D:/docs"

  # 直接指定测试集进行问答测试
  python main.py --qa --testset "D:/tests/questions.xlsx"
        """,
    )

    parser.add_argument(
        "command",
        nargs="?",
        help="自然语言命令，如'帮我测试香港海关知识库'",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        help="场景名称，如 hk_customs",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="仅执行文档上传",
    )
    parser.add_argument(
        "--qa",
        action="store_true",
        help="仅执行问答测试",
    )
    parser.add_argument(
        "--path",
        type=str,
        help="文档目录路径（用于直接上传）",
    )
    parser.add_argument(
        "--testset",
        type=str,
        help="测试集 Excel 文件路径（用于直接问答测试）",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件目录",
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config) if args.config else load_config()

    # 创建 Agent
    agent = AutoTestAgent(config)

    if args.command:
        # 使用自然语言命令
        print(f"执行命令：{args.command}")
        result = await agent.execute(args.command)
    elif args.upload:
        # 仅执行文档上传
        if args.scenario:
            print(f"执行文档上传场景：{args.scenario}")
            result = await agent.upload_documents(scenario_name=args.scenario)
        elif args.path:
            print(f"执行文档上传，目录：{args.path}")
            result = await agent.upload_documents(base_path=args.path)
        else:
            print("错误：--upload 需要指定 --scenario 或 --path")
            sys.exit(1)
        return
    elif args.qa:
        # 仅执行问答测试
        if args.scenario:
            print(f"执行问答测试场景：{args.scenario}")
            result = await agent.run_qa_tests(scenario_name=args.scenario)
        elif args.testset:
            print(f"执行问答测试，测试集：{args.testset}")
            result = await agent.run_qa_tests(testset_path=args.testset)
        else:
            print("错误：--qa 需要指定 --scenario 或 --testset")
            sys.exit(1)
        return
    else:
        # 无参数时显示帮助
        parser.print_help()
        sys.exit(0)

    # 输出结果
    if result.success:
        print(f"\n[OK] {result.message}")
        if result.report_path:
            print(f"  报告路径：{result.report_path}")
    else:
        print(f"\n[FAIL] {result.message}")
        if result.error:
            print(f"  错误：{result.error}")
        sys.exit(1)


def main():
    """主入口"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\n用户中断执行")
        sys.exit(130)
    except Exception as e:
        print(f"\n[FAIL] 执行失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
