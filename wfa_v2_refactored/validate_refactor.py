#!/usr/bin/env python3
"""
WFA重构版本验证脚本
测试所有模块是否能正常导入和基本功能是否可用
"""

import sys
from pathlib import Path


# 添加当前目录到路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))


def test_imports():
    """测试模块导入"""
    print("🔍 测试模块导入...")

    try:
        from data_types import BacktestResult, WFAConfig, WFAResult, WFAWindow

        print(" data_types 模块导入成功")

        from freqtrade_parameter_generator import FreqtradeParameterGenerator

        print(" freqtrade_parameter_generator 模块导入成功")

        from backtest_executor import BacktestExecutor

        print(" backtest_executor 模块导入成功")

        from wfa_analyzer import WFAAnalyzer

        print(" wfa_analyzer 模块导入成功")

        from result_analyzer import ResultAnalyzer

        print(" result_analyzer 模块导入成功")

        print(" 所有模块导入成功！")
        return True

    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False


def test_basic_functionality():
    """测试基本功能"""
    print("\n🔧 测试基本功能...")

    try:
        from data_types import WFAConfig, WFAWindow

        # 测试配置创建
        config = WFAConfig(
            strategy_name="TestStrategy",
            config_path="./test_config.json",
            start_date="20230101",
            end_date="20231231",
        )
        print(f" WFAConfig 创建成功: {config.strategy_name}")

        # 测试窗口创建
        window = WFAWindow(
            window_id=1,
            is_start="20230101",
            is_end="20230630",
            oos_start="20230701",
            oos_end="20230930",
        )
        print(
            f" WFAWindow 创建成功: IS={window.get_is_timerange()}, OOS={window.get_oos_timerange()}"
        )

        return True

    except Exception as e:
        print(f"❌ 基本功能测试失败: {e}")
        return False


def test_analyzer_creation():
    """测试分析器创建（不执行实际分析）"""
    print("\n🏗️  测试分析器创建...")

    try:
        from data_types import WFAConfig
        from result_analyzer import ResultAnalyzer
        from wfa_analyzer import WFAAnalyzer

        # 创建测试配置
        config = WFAConfig(
            strategy_name="TestStrategy",
            config_path="./dummy_config.json",  # 不需要真实存在
        )

        # 尝试创建结果分析器（这个不依赖freqtrade）
        result_analyzer = ResultAnalyzer(config)
        print(" ResultAnalyzer 创建成功")

        print(" 分析器创建测试完成！")
        return True

    except Exception as e:
        print(f"❌ 分析器创建测试失败: {e}")
        return False


def main():
    """主函数"""
    print(" WFA重构版本验证测试")
    print("=" * 50)

    success_count = 0
    total_tests = 3

    # 测试1: 模块导入
    if test_imports():
        success_count += 1

    # 测试2: 基本功能
    if test_basic_functionality():
        success_count += 1

    # 测试3: 分析器创建
    if test_analyzer_creation():
        success_count += 1

    print("\n" + "=" * 50)
    print(f"📊 测试结果: {success_count}/{total_tests} 通过")

    if success_count == total_tests:
        print(" 所有测试通过！重构版本基本功能正常")
        print("\n 下一步:")
        print("  1. 确保 freqtrade 环境已正确配置")
        print("  2. 准备策略文件和配置文件")
        print("  3. 运行 python main.py 开始完整分析")
    else:
        print("  部分测试失败，请检查模块实现")

    print("=" * 50)


if __name__ == "__main__":
    main()
