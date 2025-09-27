#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WFA策略评测器重构版本 - 主入口模块
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path


# 添加当前目录到 Python 路径，确保可以导入本地模块
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 添加freqtrade主目录到Python路径
freqtrade_dir = current_dir.parent / "freqtrade"
if freqtrade_dir.exists():
    sys.path.insert(0, str(freqtrade_dir.parent))
    print(f"[DEBUG] 添加freqtrade路径: {freqtrade_dir.parent}")
else:
    print(f"[WARNING] freqtrade目录不存在: {freqtrade_dir}")

try:
    from .data_types import WFAConfig
    from .result_analyzer import ResultAnalyzer
    from .wfa_analyzer import WFAAnalyzer
except ImportError:
    from data_types import WFAConfig
    from result_analyzer import ResultAnalyzer
    from wfa_analyzer import WFAAnalyzer


# 设置日志
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"wfa_evaluation_refactored_{current_time}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


def load_wfa_config(config_file: str = "wfa_config_v2.json") -> WFAConfig:
    """加载WFA配置文件"""
    try:
        # 首先尝试从父目录加载配置文件
        config_path = Path(__file__).parent.parent / config_file

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            logger.info(f"[CONFIG] 已加载配置文件: {config_path}")
        else:
            logger.warning(f"[CONFIG] 配置文件不存在，使用默认配置: {config_path}")
            config_data = {}

        # 策略配置
        strategy_config = config_data.get("strategy_config", {})
        strategy_name = strategy_config.get("strategy_name", "Strategy_Simple_Indicator_Test")
        config_path_str = strategy_config.get("config_path", "./user_data/config.json")

        # WFA参数配置
        wfa_params = config_data.get("wfa_parameters", {})

        # 优化配置
        optimization_config = config_data.get("optimization_settings", {})

        # 创建WFAConfig对象
        wfa_config = WFAConfig(
            strategy_name=strategy_name,
            config_path=config_path_str,
            timeframe=strategy_config.get("timeframe", "30m"),
            is_window_months=wfa_params.get("is_window_months", 24),
            oos_window_months=wfa_params.get("oos_window_months", 6),
            roll_step_months=wfa_params.get("roll_step_months", 6),
            start_date=wfa_params.get("start_date", "20220101"),
            end_date=wfa_params.get("end_date", "20241201"),
            optimization_method=optimization_config.get("method", "random"),
            max_param_combinations=optimization_config.get("max_combinations", 300),
        )

        return wfa_config

    except Exception as e:
        logger.error(f"[ERROR] 读取配置文件失败: {e}")
        logger.info("[CONFIG] 使用默认配置")
        return WFAConfig()


def main():
    """主函数"""
    print("🔍 前向分析 (Walk-Forward Analysis) 策略评测器 重构版本")
    print("=" * 80)
    print("✨ 新特性：")
    print("  - 模块化设计，职责分离")
    print("  - 复用 Freqtrade 参数系统")
    print("  - 自动参数检测和组合生成")
    print("=" * 80)
    print(f"📝 日志文件: {log_filename}")
    print("=" * 80)

    try:
        # 加载配置
        config = load_wfa_config()

        print(f"🎯 策略: {config.strategy_name}")
        print(f"⏰ IS窗口: {config.is_window_months}个月")
        print(f"📊 OOS窗口: {config.oos_window_months}个月")
        print(f"🔄 滚动步长: {config.roll_step_months}个月")
        print(f"📅 分析期间: {config.start_date} - {config.end_date}")
        print(f"⚙️ 优化方法: {config.optimization_method}")
        print(f"📈 参数组合数: {config.max_param_combinations}")
        print("=" * 80)

        # 检查配置文件
        if not os.path.exists(config.config_path):
            print(f"❌ 配置文件不存在: {config.config_path}")
            return

        # 创建WFA分析器
        wfa_analyzer = WFAAnalyzer(config)

        # 创建结果分析器
        result_analyzer = ResultAnalyzer(config)

        # 运行WFA分析
        print("\n🚀 开始WFA分析...")
        results = wfa_analyzer.run_full_analysis()

        if results:
            print(f"\n📊 分析结果统计...")
            analysis = result_analyzer.analyze_results(results)

            print(f"\n💾 保存分析结果...")
            result_analyzer.save_results(results, analysis)

            print(f"\n✅ WFA分析完成！")
            print(f"📊 总窗口数: {len(results)}")
            print(
                f"🎯 成功窗口数: {len([r for r in results if r.optimization_success and r.oos_backtest_success])}"
            )
            print(f"📝 详细报告请查看日志文件: {log_filename}")
        else:
            print(f"\n❌ WFA分析失败！请检查日志文件: {log_filename}")

    except Exception as e:
        print(f"\n💥 程序运行出错: {e}")
        logger.error(f"主程序错误: {e}")
        import traceback

        logger.error(f"详细错误: {traceback.format_exc()}")


if __name__ == "__main__":
    main()
