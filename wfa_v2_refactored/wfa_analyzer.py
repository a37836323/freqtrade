#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WFA分析器模块
负责WFA窗口管理和优化分析
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any


try:
    from .backtest_executor import BacktestExecutor
    from .data_types import BacktestResult, WFAConfig, WFAResult, WFAWindow
    from .freqtrade_parameter_generator import FreqtradeParameterGenerator
except ImportError:
    from backtest_executor import BacktestExecutor
    from data_types import BacktestResult, WFAConfig, WFAResult, WFAWindow
    from freqtrade_parameter_generator import FreqtradeParameterGenerator


logger = logging.getLogger(__name__)


class WFAAnalyzer:
    """WFA分析器"""

    def __init__(self, config: WFAConfig):
        self.config = config
        # 初始化回测执行器
        self.backtest_executor = BacktestExecutor(
            config.strategy_name, config.config_path, config.timeframe
        )
        # 初始化参数生成器
        self.param_generator = FreqtradeParameterGenerator(config.strategy_name, config.config_path)
        # 初始化WFA结果列表
        self.wfa_results: list[WFAResult] = []

    def generate_windows(self) -> list[WFAWindow]:
        """生成所有WFA窗口配置"""
        windows = []
        window_id = 1

        # 转换日期
        start_dt = datetime.strptime(self.config.start_date, "%Y%m%d")
        end_dt = datetime.strptime(self.config.end_date, "%Y%m%d")

        current_dt = start_dt

        while True:
            # IS窗口
            is_start = current_dt
            is_end = current_dt + timedelta(days=self.config.is_window_months * 30.44)

            # OOS窗口
            oos_start = is_end + timedelta(days=1)
            oos_end = oos_start + timedelta(days=self.config.oos_window_months * 30.44)

            # 检查是否超出结束日期
            if oos_end > end_dt:
                break

            window = WFAWindow(
                window_id=window_id,
                is_start=is_start.strftime("%Y%m%d"),
                is_end=is_end.strftime("%Y%m%d"),
                oos_start=oos_start.strftime("%Y%m%d"),
                oos_end=oos_end.strftime("%Y%m%d"),
            )

            windows.append(window)
            window_id += 1

            # 滚动到下一个窗口
            current_dt += timedelta(days=self.config.roll_step_months * 30.44)

        logger.info(f"[WFA] 生成了 {len(windows)} 个WFA窗口")
        return windows

    def optimize_window(
        self, window: WFAWindow
    ) -> tuple[bool, dict[str, Any] | None, dict[str, Any] | None, list[BacktestResult]]:
        """在IS窗口上优化参数"""
        logger.info(f"[OPTIMIZE] 窗口 {window.window_id}: 开始IS优化 {window.get_is_timerange()}")

        # 生成参数组合
        param_combinations = self._generate_parameter_combinations()
        logger.info(
            f"[OPTIMIZE] 窗口 {window.window_id}: 生成了 {len(param_combinations)} 个参数组合"
        )

        # 运行回测
        results = []
        successful_results = []

        for i, params in enumerate(param_combinations, 1):
            if i % 50 == 0:
                logger.info(
                    f"[PROGRESS] 窗口 {window.window_id}: 完成 {i}/{len(param_combinations)} 个参数测试"
                )

            result = self.backtest_executor.run_backtest(window.get_is_timerange(), params)
            results.append(result)

            if result.success:
                successful_results.append(result)

        logger.info(
            f"[OPTIMIZE] 窗口 {window.window_id}: 成功测试 {len(successful_results)}/{len(param_combinations)} 个参数组合"
        )

        if not successful_results:
            logger.error(f"[ERROR] 窗口 {window.window_id}: 没有成功的参数组合")
            return False, None, None, results

        # 选择最佳参数（基于Sharpe比率）
        best_result = max(successful_results, key=lambda x: x.performance.get("sharpe", -999))

        logger.info(
            f"[OPTIMIZE] 窗口 {window.window_id}: 最佳Sharpe = {best_result.performance.get('sharpe', 0):.3f}"
        )
        logger.info(
            f"[OPTIMIZE] 窗口 {window.window_id}: 最佳收益率 = {best_result.performance.get('profit_total', 0):.2%}"
        )

        return True, best_result.params, best_result.performance, results

    def run_oos_backtest(
        self, window: WFAWindow, best_params: dict[str, Any]
    ) -> tuple[bool, dict[str, Any] | None]:
        """在OOS窗口上运行回测"""
        logger.info(f"[OOS] 窗口 {window.window_id}: 开始OOS回测 {window.get_oos_timerange()}")

        result = self.backtest_executor.run_backtest(window.get_oos_timerange(), best_params)

        if result.success:
            logger.info(
                f"[OOS] 窗口 {window.window_id}: OOS收益率 = {result.performance.get('profit_total', 0):.2%}"
            )
            logger.info(
                f"[OOS] 窗口 {window.window_id}: OOS Sharpe = {result.performance.get('sharpe', 0):.3f}"
            )
            return True, result.performance
        else:
            logger.error(f"[OOS] 窗口 {window.window_id}: OOS回测失败 - {result.error_message}")
            return False, None

    def run_full_analysis(self) -> list[WFAResult]:
        """运行完整的WFA分析"""
        logger.info("[WFA] 开始前向分析（重构版本）...")

        # 生成所有窗口
        windows = self.generate_windows()

        if not windows:
            logger.error("[ERROR] 没有生成任何WFA窗口")
            return []

        logger.info(f"[WFA] 将处理 {len(windows)} 个窗口")

        # 逐个处理窗口
        for i, window in enumerate(windows, 1):
            logger.info(f"\n{'=' * 80}")
            logger.info(f"[WFA] 处理窗口 {i}/{len(windows)} (ID: {window.window_id})")
            logger.info(f"[WFA] IS期间: {window.get_is_timerange()}")
            logger.info(f"[WFA] OOS期间: {window.get_oos_timerange()}")
            logger.info(f"{'=' * 80}")

            result = WFAResult(window=window, is_results=[])

            # 步骤1: IS窗口优化
            optimization_success, best_params, best_performance, is_results = self.optimize_window(
                window
            )
            result.is_results = is_results
            result.optimization_success = optimization_success

            if optimization_success:
                result.best_params = best_params
                result.is_best_performance = best_performance

                # 步骤2: OOS窗口回测
                oos_success, oos_performance = self.run_oos_backtest(window, best_params)
                result.oos_backtest_success = oos_success
                result.oos_performance = oos_performance

                if not oos_success:
                    result.error_message = "OOS回测失败"
            else:
                result.error_message = "IS优化失败"

            self.wfa_results.append(result)

            # 短暂延迟
            time.sleep(1)

        return self.wfa_results

    def _generate_parameter_combinations(self) -> list[dict[str, Any]]:
        """生成参数组合"""
        if self.config.optimization_method == "grid":
            return self.param_generator.generate_grid_combinations(
                self.config.max_param_combinations
            )
        else:
            return self.param_generator.generate_random_combinations(
                self.config.max_param_combinations
            )
