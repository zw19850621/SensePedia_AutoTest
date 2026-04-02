"""
调试脚本 - 测试单个问题的完整问答流程
"""

import asyncio
import logging
import sys

from src.core.config import load_config
from src.core.auth import AuthManager
from src.drivers.qa_driver import QADriver

# 配置日志输出
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

async def main():
    """测试单个问题的完整问答流程"""
    print("=" * 80)
    print("开始测试问答流程")
    print("=" * 80)

    # 加载配置
    config = load_config()
    auth_manager = AuthManager(config)
    qa_driver = QADriver(config, auth_manager)

    # 测试问题
    question = "我的包裹 HK00618273205 由 5/11 開始在海關查驗，直至現在仍未放行"

    try:
        # 执行单次测试
        result = await qa_driver.run_single_qa_test(
            question=question,
            knowledge_base_id="ALL_KB",
            session_title=question,  # 使用问题作为标题
        )

        print("\n" + "=" * 80)
        print("测试完成!")
        print("=" * 80)
        print(f"问题：{result.question}")
        print(f"成功：{result.success}")
        print(f"答案：{result.answer[:200] if result.answer else '无答案'}...")
        print(f"响应时间：{result.response_time:.2f}s")
        print(f"会话 ID: {result.session_id}")
        print(f"消息 ID: {result.message_id}")
        if result.error:
            print(f"错误：{result.error}")

    except Exception as e:
        print(f"\n测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
