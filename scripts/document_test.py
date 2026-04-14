#!/usr/bin/env python
"""
文档上传测试脚本

用法:
    python scripts/document_test.py                 # 直接运行（使用第一个启用的场景）
    python scripts/document_test.py --scenario hk_customs
    python scripts/document_test.py --path "D:/docs"
"""

import asyncio
import sys
import argparse
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import load_config
from src.core.auth import AuthManager
from src.drivers.document_driver import DocumentDriver

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
        description="文档上传测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 直接运行（使用第一个启用的场景）
  python scripts/document_test.py

  # 指定场景
  python scripts/document_test.py --scenario hk_customs

  # 直接指定文档目录
  python scripts/document_test.py --path "D:/docs"
        """
    )

    parser.add_argument(
        "--scenario",
        type=str,
        help="测试场景名称"
    )
    parser.add_argument(
        "--path",
        type=str,
        help="文档目录路径"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=0,
        help="最大并发数（默认使用配置值）"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件目录"
    )

    args = parser.parse_args()

    # 加载配置
    config_path = args.config if args.config else None
    config = load_config(config_path)

    # 初始化认证管理器
    auth_manager = AuthManager(config)
    await auth_manager.login()

    # 初始化驱动器
    driver = DocumentDriver(config, auth_manager)

    # 确定使用哪个场景或目录
    if args.scenario:
        # 指定场景
        scenario_name = args.scenario
    else:
        # 使用第一个启用的场景
        scenario_name = None
        for name, data in config.scenarios.items():
            if data.get("enabled", True) and data.get("document_upload", {}).get("enabled", True):
                scenario_name = name
                break

    if scenario_name:
        scenario = config.get_scenario(scenario_name)
        if not scenario or not scenario.document_upload:
            print(f"错误：场景 '{scenario_name}' 未找到或未配置 document_upload")
            sys.exit(1)

        upload_config = scenario.document_upload
        concurrency = args.concurrency if args.concurrency > 0 else upload_config.max_concurrent

        print(f"\n{'='*60}")
        print(f"执行文档上传测试 - 场景：{scenario_name}")
        print(f"{'='*60}")
        print(f"目录：{upload_config.base_path}")
        print(f"文件类型：{', '.join(upload_config.file_types)}")
        print(f"并发数：{concurrency}")
        print(f"{'='*60}\n")

        result = await driver.batch_upload(
            upload_config=upload_config,
            max_concurrent=concurrency,
            show_progress=True
        )
    elif args.path:
        # 直接指定目录
        base_path = Path(args.path)
        if not base_path.exists():
            print(f"错误：目录不存在：{base_path}")
            sys.exit(1)

        concurrency = args.concurrency if args.concurrency > 0 else 3

        print(f"\n{'='*60}")
        print(f"执行文档上传测试")
        print(f"{'='*60}")
        print(f"目录：{base_path}")
        print(f"并发数：{concurrency}")
        print(f"{'='*60}\n")

        # 创建临时配置
        from src.core.config import DocumentUploadConfig
        upload_config = DocumentUploadConfig(
            base_path=str(base_path),
            file_types=["pdf", "doc", "docx", "txt", "md"],
            language="zh-cn",
            visibility="private",
            max_concurrent=concurrency
        )

        result = await driver.batch_upload(
            upload_config=upload_config,
            max_concurrent=concurrency,
            show_progress=True
        )
    else:
        print("错误：未找到可用的场景配置，也未指定 --path")
        print("请在 config/scenarios.yaml 中配置场景，或使用 --scenario 指定场景")
        sys.exit(1)

    # 输出结果摘要
    print(f"\n{'='*60}")
    print(f"测试完成")
    print(f"{'='*60}")
    print(f"总数：{result.total} | 成功：{result.success} | 失败：{result.failed}")
    print(f"成功率：{result.success_rate:.1%} | 总耗时：{result.duration:.2f}s")

    if result.failed > 0:
        print(f"\n失败文件:")
        for r in result.results:
            if not r.success:
                print(f"  - {r.file_name}: {r.error}")

    print(f"{'='*60}\n")

    # 返回退出码
    sys.exit(0 if result.success == result.total else 1)


if __name__ == "__main__":
    asyncio.run(main())
