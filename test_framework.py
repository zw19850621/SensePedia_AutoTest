"""
测试脚本 - 验证框架功能
"""

import asyncio
from src.agents import AutoTestAgent
from src.core import load_config


async def test_config():
    """测试配置加载"""
    print("=" * 50)
    print("测试配置加载")
    print("=" * 50)

    config = load_config()
    print(f"基础 URL: {config.base_urls}")
    print(f"场景列表：{list(config.scenarios.keys())}")
    print(f"认证用户名：{config.auth.username}")
    print()


async def test_auth():
    """测试认证登录"""
    print("=" * 50)
    print("测试认证登录")
    print("=" * 50)

    config = load_config()
    auth_manager = AuthManager(config)

    try:
        token = await auth_manager.login()
        print(f"登录成功！Token: {token[:50]}...")
        user = auth_manager.get_current_user()
        if user:
            print(f"用户：{user.get('username')} ({user.get('display_name')})")
    except Exception as e:
        print(f"登录失败：{e}")
    print()


async def test_agent():
    """测试 Agent 意图解析"""
    print("=" * 50)
    print("测试 Agent 意图解析")
    print("=" * 50)

    config = load_config()
    agent = AutoTestAgent(config)

    test_commands = [
        "帮我测试香港海关知识库",
        "上传香港海关的文档",
        "测试海关知识库的问答",
        "run hk customs test",
    ]

    for cmd in test_commands:
        intent = agent._parse_intent(cmd)
        print(f"命令：{cmd}")
        print(f"  -> 动作：{intent.action}, 场景：{intent.scenario}")
    print()


async def main():
    """主函数"""
    await test_config()
    await test_auth()
    await test_agent()

    print("=" * 50)
    print("所有测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    from src.core.auth import AuthManager
    asyncio.run(main())
