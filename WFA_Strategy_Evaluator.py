#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前向分析 (Walk-Forward Analysis) 策略评测器
专为Strategy_Simple_Indicator_Test策略设计

实现完整的滚动窗口优化和测试流程，提供严谨的策略验证
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# 设置日志
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"wfa_evaluation_{current_time}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


@dataclass
class WFAWindow:
    """WFA窗口配置"""

    window_id: int
    is_start: str  # IS窗口开始时间 YYYYMMDD
    is_end: str  # IS窗口结束时间 YYYYMMDD
    oos_start: str  # OOS窗口开始时间 YYYYMMDD
    oos_end: str  # OOS窗口结束时间 YYYYMMDD

    def get_is_timerange(self) -> str:
        return f"{self.is_start}-{self.is_end}"

    def get_oos_timerange(self) -> str:
        return f"{self.oos_start}-{self.oos_end}"


@dataclass
class WFAResult:
    """单个WFA窗口的结果"""

    window: WFAWindow
    is_optimization_success: bool
    oos_backtest_success: bool
    best_params: Optional[Dict[str, Any]] = None
    is_performance: Optional[Dict[str, Any]] = None
    oos_performance: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class WFAStrategyEvaluator:
    """前向分析策略评测器"""

    def __init__(
        self,
        strategy_name: str = "Strategy_Simple_Indicator_Test",
        config_path: str = "./user_data/config.json",
        timeframe: str = "30m",
        is_window_months: int = 24,  # IS窗口长度（月）
        oos_window_months: int = 6,  # OOS窗口长度（月）
        roll_step_months: int = 6,  # 滚动步长（月）
        start_date: str = "20220101",  # 分析开始日期
        end_date: str = "20241201",  # 分析结束日期
    ):
        self.strategy_name = strategy_name
        self.config_path = config_path
        self.timeframe = timeframe
        self.is_window_months = is_window_months
        self.oos_window_months = oos_window_months
        self.roll_step_months = roll_step_months
        self.start_date = start_date
        self.end_date = end_date

        # 结果存储
        self.wfa_results: List[WFAResult] = []
        self.combined_oos_trades: List[Dict[str, Any]] = []

        # 验证配置
        self._validate_config()

        logger.info(f"[INIT] WFA策略评测器初始化完成")
        logger.info(f"[CONFIG] 策略: {self.strategy_name}")
        logger.info(f"[CONFIG] IS窗口: {self.is_window_months}个月")
        logger.info(f"[CONFIG] OOS窗口: {self.oos_window_months}个月")
        logger.info(f"[CONFIG] 滚动步长: {self.roll_step_months}个月")
        logger.info(f"[CONFIG] 分析期间: {self.start_date} - {self.end_date}")

    def _validate_config(self):
        """验证配置参数"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        # 验证日期格式
        try:
            datetime.strptime(self.start_date, "%Y%m%d")
            datetime.strptime(self.end_date, "%Y%m%d")
        except ValueError as e:
            raise ValueError(f"日期格式错误: {e}")

        if self.is_window_months < 12:
            logger.warning("[WARNING] IS窗口少于12个月，可能导致优化不充分")

        if self.oos_window_months < 3:
            logger.warning("[WARNING] OOS窗口少于3个月，可能无法充分验证策略")

    def _generate_windows(self) -> List[WFAWindow]:
        """生成所有WFA窗口配置"""
        windows = []
        window_id = 1

        # 转换日期
        start_dt = datetime.strptime(self.start_date, "%Y%m%d")
        end_dt = datetime.strptime(self.end_date, "%Y%m%d")

        current_dt = start_dt

        while True:
            # IS窗口
            is_start = current_dt
            is_end = current_dt + timedelta(days=self.is_window_months * 30.44)  # 平均月天数

            # OOS窗口
            oos_start = is_end + timedelta(days=1)
            oos_end = oos_start + timedelta(days=self.oos_window_months * 30.44)

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
            current_dt += timedelta(days=self.roll_step_months * 30.44)

        logger.info(f"[WINDOWS] 生成了 {len(windows)} 个WFA窗口")
        return windows

    def _run_hyperopt_optimization(
        self, window: WFAWindow, optimization_config: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """在IS窗口上运行超参数优化"""
        logger.info(f"[HYPEROPT] 窗口 {window.window_id}: 开始IS优化 {window.get_is_timerange()}")

        # 使用传入的优化配置，否则使用默认值
        if optimization_config is None:
            optimization_config = {}

        try:
            from freqtrade.commands.optimize_commands import setup_optimize_configuration
            from freqtrade.enums import RunMode
            from freqtrade.optimize.hyperopt import Hyperopt

            # 构建超参数优化参数
            args = {
                "config": [self.config_path],
                "strategy": self.strategy_name,
                "timeframe": self.timeframe,
                "timerange": window.get_is_timerange(),
                "hyperopt_epochs": optimization_config.get("hyperopt_epochs", 300),
                "hyperopt_random_state": optimization_config.get("random_state", 42),
                "spaces": optimization_config.get("spaces", ["buy", "sell"]),
                "verbosity": 0,
                "logfile": None,
                "hyperopt_min_trades": optimization_config.get("hyperopt_min_trades", 50),
                "hyperopt_loss": optimization_config.get("hyperopt_loss", "SharpeHyperOptLoss"),
            }

            # 设置配置
            config = setup_optimize_configuration(args, RunMode.HYPEROPT)

            # 创建超参数优化实例
            hyperopt = Hyperopt(config)

            # 运行优化
            hyperopt.start()

            # 获取最佳参数
            if hasattr(hyperopt, "hyperopt_table") and hyperopt.hyperopt_table is not None:
                # 从优化结果中提取最佳参数
                best_result = hyperopt.hyperopt_table.iloc[0]  # 第一行是最佳结果

                best_params = {
                    "buy_params": {},
                    "sell_params": {},
                }

                # 提取buy参数
                for key, value in best_result.items():
                    if key.startswith("buy_"):
                        best_params["buy_params"][key] = value
                    elif key.startswith("sell_"):
                        best_params["sell_params"][key] = value

                logger.info(f"[SUCCESS] 窗口 {window.window_id}: IS优化完成")
                return True, best_params, None
            else:
                logger.error(f"[ERROR] 窗口 {window.window_id}: 优化结果为空")
                return False, None, "优化结果为空"

        except Exception as e:
            error_msg = f"超参数优化失败: {str(e)}"
            logger.error(f"[ERROR] 窗口 {window.window_id}: {error_msg}")
            import traceback

            logger.error(f"[ERROR] 详细错误: {traceback.format_exc()}")
            return False, None, error_msg
        finally:
            # 清理资源
            if "hyperopt" in locals():
                try:
                    hyperopt.cleanup()
                except:
                    pass

    def _run_oos_backtest(
        self, window: WFAWindow, params: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """使用优化参数在OOS窗口上运行回测"""
        logger.info(f"[BACKTEST] 窗口 {window.window_id}: 开始OOS回测 {window.get_oos_timerange()}")

        try:
            # 首先更新策略参数
            if not self._update_strategy_params(params):
                return False, None, "更新策略参数失败"

            from freqtrade.commands.optimize_commands import setup_optimize_configuration
            from freqtrade.enums import RunMode
            from freqtrade.optimize.backtesting import Backtesting

            # 构建回测参数
            args = {
                "config": [self.config_path],
                "strategy": self.strategy_name,
                "timeframe": self.timeframe,
                "timerange": window.get_oos_timerange(),
                "verbosity": 0,
                "logfile": None,
                "export": "trades",  # 导出交易记录
                "cache": "none",
            }

            # 设置配置
            config = setup_optimize_configuration(args, RunMode.BACKTEST)

            # 创建回测实例
            backtesting = Backtesting(config)

            # 运行回测
            backtesting.start()

            # 获取结果
            if backtesting.results is None:
                return False, None, "回测结果为None"

            if "strategy" not in backtesting.results:
                return False, None, "回测结果中没有strategy键"

            strategy_results = backtesting.results["strategy"]
            if self.strategy_name not in strategy_results:
                return False, None, f"未找到策略 {self.strategy_name}"

            result = strategy_results[self.strategy_name]

            # 提取关键指标
            if isinstance(result, dict):
                performance = self._extract_performance_metrics(result)

                # 保存交易记录
                if hasattr(backtesting, "processed") and backtesting.processed:
                    trades = backtesting.processed
                    # 为每笔交易添加窗口标识
                    for trade in trades:
                        trade["wfa_window_id"] = window.window_id
                        trade["is_oos"] = True
                    self.combined_oos_trades.extend(trades)

                logger.info(
                    f"[SUCCESS] 窗口 {window.window_id}: OOS回测完成，收益率 {performance.get('profit_total', 0):.2%}"
                )
                return True, performance, None
            else:
                return False, None, "回测结果格式错误"

        except Exception as e:
            error_msg = f"OOS回测失败: {str(e)}"
            logger.error(f"[ERROR] 窗口 {window.window_id}: {error_msg}")
            import traceback

            logger.error(f"[ERROR] 详细错误: {traceback.format_exc()}")
            return False, None, error_msg
        finally:
            # 清理资源
            if "backtesting" in locals():
                try:
                    backtesting.cleanup()
                except:
                    pass

    def _update_strategy_params(self, params: Dict[str, Any]) -> bool:
        """更新策略参数JSON文件"""
        try:
            strategy_json_path = f"./user_data/strategies/{self.strategy_name}.json"

            # 读取或创建策略配置
            if os.path.exists(strategy_json_path):
                with open(strategy_json_path, "r", encoding="utf-8") as f:
                    strategy_config = json.load(f)
            else:
                strategy_config = {
                    "strategy_name": self.strategy_name,
                    "params": {},
                    "ft_stratparam_v": 1,
                    "export_time": datetime.now().isoformat(),
                }

            # 更新参数
            if "buy_params" in params and params["buy_params"]:
                if "buy" not in strategy_config["params"]:
                    strategy_config["params"]["buy"] = {}
                strategy_config["params"]["buy"].update(params["buy_params"])

            if "sell_params" in params and params["sell_params"]:
                if "sell" not in strategy_config["params"]:
                    strategy_config["params"]["sell"] = {}
                strategy_config["params"]["sell"].update(params["sell_params"])

            # 更新其他参数类型
            for param_type in ["roi", "stoploss", "trailing", "max_open_trades", "protection"]:
                if param_type in params and params[param_type]:
                    strategy_config["params"][param_type] = params[param_type]

            # 更新时间戳
            strategy_config["export_time"] = datetime.now().isoformat()

            # 写入文件
            with open(strategy_json_path, "w", encoding="utf-8") as f:
                json.dump(strategy_config, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            logger.error(f"[ERROR] 更新策略参数失败: {e}")
            return False

    def _extract_performance_metrics(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """提取性能指标"""
        return {
            # 基础交易指标
            "total_trades": result.get("total_trades", 0),
            "profit_total": result.get("profit_total", 0),
            "profit_total_abs": result.get("profit_total_abs", 0),
            "wins": result.get("wins", 0),
            "draws": result.get("draws", 0),
            "losses": result.get("losses", 0),
            "win_rate": result.get("wins", 0) / max(result.get("total_trades", 1), 1),
            # 收益指标
            "cagr": result.get("cagr", 0),
            "avg_profit": result.get("profit_mean", 0),
            "profit_median": result.get("profit_median", 0),
            "expectancy": result.get("expectancy", 0),
            "profit_factor": result.get("profit_factor", 0),
            # 风险指标
            "sharpe": result.get("sharpe", 0),
            "sortino": result.get("sortino", 0),
            "calmar": result.get("calmar", 0),
            "max_drawdown": result.get("max_drawdown_account", 0),
            "max_drawdown_abs": result.get("max_drawdown_abs", 0),
            # 持仓时间
            "avg_duration": self._parse_duration_to_minutes(result.get("holding_avg", None)),
            "winner_holding_avg": self._parse_duration_to_minutes(
                result.get("winner_holding_avg", None)
            ),
            "loser_holding_avg": self._parse_duration_to_minutes(
                result.get("loser_holding_avg", None)
            ),
            # 连胜连败
            "max_consecutive_wins": result.get("max_consecutive_wins", 0),
            "max_consecutive_losses": result.get("max_consecutive_losses", 0),
            # 资金管理
            "starting_balance": result.get("starting_balance", 0),
            "final_balance": result.get("final_balance", 0),
            "avg_stake_amount": result.get("avg_stake_amount", 0),
            "total_volume": result.get("total_volume", 0),
            # 市场相关
            "market_change": result.get("market_change", 0),
            "trades_per_day": result.get("trades_per_day", 0),
            "backtest_days": result.get("backtest_days", 0),
        }

    def _parse_duration_to_minutes(self, duration) -> float:
        """解析持仓时间为分钟数"""
        try:
            if duration is None:
                return 0.0

            if hasattr(duration, "total_seconds"):
                return duration.total_seconds() / 60.0

            if isinstance(duration, str):
                if not duration:
                    return 0.0

                if ":" in duration:
                    parts = duration.split(":")
                    if len(parts) == 3:  # HH:MM:SS
                        hours = int(parts[0])
                        minutes = int(parts[1])
                        seconds = int(parts[2])
                        return hours * 60 + minutes + seconds / 60
                    elif len(parts) == 2:  # MM:SS
                        minutes = int(parts[0])
                        seconds = int(parts[1])
                        return minutes + seconds / 60

                return float(duration)

            return float(duration)

        except Exception:
            return 0.0

    def run_wfa_analysis(
        self, optimization_config: Optional[Dict[str, Any]] = None
    ) -> List[WFAResult]:
        """运行完整的WFA分析"""
        logger.info("[WFA] 开始前向分析...")

        # 生成所有窗口
        windows = self._generate_windows()

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

            result = WFAResult(
                window=window, is_optimization_success=False, oos_backtest_success=False
            )

            # 步骤1: IS窗口优化
            is_success, best_params, is_error = self._run_hyperopt_optimization(
                window, optimization_config
            )
            result.is_optimization_success = is_success

            if not is_success:
                result.error_message = f"IS优化失败: {is_error}"
                logger.error(f"[ERROR] 窗口 {window.window_id} IS优化失败，跳过")
                self.wfa_results.append(result)
                continue

            result.best_params = best_params

            # 步骤2: 使用最佳参数进行IS窗口回测（验证优化结果）
            is_backtest_success, is_performance, is_backtest_error = self._run_oos_backtest(
                WFAWindow(
                    window_id=window.window_id,
                    is_start=window.is_start,
                    is_end=window.is_end,
                    oos_start=window.is_start,  # 使用IS时间段
                    oos_end=window.is_end,
                ),
                best_params,
            )

            if is_backtest_success:
                result.is_performance = is_performance
                logger.info(f"[IS_VERIFY] 窗口 {window.window_id} IS验证成功")
            else:
                logger.warning(f"[WARNING] 窗口 {window.window_id} IS验证失败: {is_backtest_error}")

            # 步骤3: OOS窗口回测
            oos_success, oos_performance, oos_error = self._run_oos_backtest(window, best_params)
            result.oos_backtest_success = oos_success

            if not oos_success:
                result.error_message = f"OOS回测失败: {oos_error}"
                logger.error(f"[ERROR] 窗口 {window.window_id} OOS回测失败")
            else:
                result.oos_performance = oos_performance
                logger.info(f"[SUCCESS] 窗口 {window.window_id} 完成")

            self.wfa_results.append(result)

            # 短暂延迟避免资源冲突
            time.sleep(2)

        # 保存和分析结果
        logger.info(f"\n[WFA] 所有窗口处理完成，开始结果分析...")
        self._analyze_and_save_results()

        return self.wfa_results

    def _analyze_and_save_results(self):
        """分析和保存WFA结果"""
        logger.info("[ANALYZE] 开始分析WFA结果...")

        # 统计成功率
        total_windows = len(self.wfa_results)
        is_success_count = sum(1 for r in self.wfa_results if r.is_optimization_success)
        oos_success_count = sum(1 for r in self.wfa_results if r.oos_backtest_success)
        complete_success_count = sum(
            1 for r in self.wfa_results if r.is_optimization_success and r.oos_backtest_success
        )

        logger.info(f"[STATS] 总窗口数: {total_windows}")
        logger.info(
            f"[STATS] IS优化成功: {is_success_count}/{total_windows} ({is_success_count / total_windows * 100:.1f}%)"
        )
        logger.info(
            f"[STATS] OOS回测成功: {oos_success_count}/{total_windows} ({oos_success_count / total_windows * 100:.1f}%)"
        )
        logger.info(
            f"[STATS] 完整成功: {complete_success_count}/{total_windows} ({complete_success_count / total_windows * 100:.1f}%)"
        )

        # 分析OOS性能
        successful_results = [
            r for r in self.wfa_results if r.oos_backtest_success and r.oos_performance
        ]

        if successful_results:
            self._analyze_oos_performance(successful_results)
            self._analyze_parameter_stability(successful_results)
            self._analyze_market_conditions(successful_results)

        # 保存详细结果
        self._save_detailed_results()

        # 生成报告
        self._generate_wfa_report()

    def _analyze_oos_performance(self, successful_results: List[WFAResult]):
        """分析OOS性能"""
        logger.info("[ANALYZE] 分析OOS样本外性能...")

        # 提取关键指标
        oos_profits = [r.oos_performance["profit_total"] for r in successful_results]
        oos_sharpes = [r.oos_performance["sharpe"] for r in successful_results]
        oos_max_dds = [r.oos_performance["max_drawdown"] for r in successful_results]
        oos_win_rates = [r.oos_performance["win_rate"] for r in successful_results]
        oos_profit_factors = [r.oos_performance["profit_factor"] for r in successful_results]

        # 计算统计指标
        def safe_stats(values):
            if not values:
                return 0, 0, 0, 0, 0
            return {
                "mean": np.mean(values),
                "median": np.median(values),
                "std": np.std(values),
                "min": np.min(values),
                "max": np.max(values),
                "positive_ratio": sum(1 for v in values if v > 0) / len(values),
            }

        profit_stats = safe_stats(oos_profits)
        sharpe_stats = safe_stats(oos_sharpes)
        dd_stats = safe_stats(oos_max_dds)
        win_rate_stats = safe_stats(oos_win_rates)
        pf_stats = safe_stats(oos_profit_factors)

        logger.info(f"[OOS_PERFORMANCE] 基于 {len(successful_results)} 个成功窗口的统计:")
        logger.info(
            f"  收益率 - 平均: {profit_stats['mean']:.2%}, 中位数: {profit_stats['median']:.2%}, 标准差: {profit_stats['std']:.2%}"
        )
        logger.info(
            f"  收益率 - 最小: {profit_stats['min']:.2%}, 最大: {profit_stats['max']:.2%}, 正收益比例: {profit_stats['positive_ratio']:.1%}"
        )
        logger.info(
            f"  Sharpe - 平均: {sharpe_stats['mean']:.3f}, 中位数: {sharpe_stats['median']:.3f}, 标准差: {sharpe_stats['std']:.3f}"
        )
        logger.info(
            f"  最大回撤 - 平均: {abs(dd_stats['mean']):.2%}, 中位数: {abs(dd_stats['median']):.2%}, 最大: {abs(dd_stats['max']):.2%}"
        )
        logger.info(
            f"  胜率 - 平均: {win_rate_stats['mean']:.1%}, 中位数: {win_rate_stats['median']:.1%}"
        )
        logger.info(f"  盈利因子 - 平均: {pf_stats['mean']:.2f}, 中位数: {pf_stats['median']:.2f}")

        # 计算累积OOS收益
        cumulative_oos_return = 1.0
        for profit in oos_profits:
            cumulative_oos_return *= 1 + profit

        total_oos_return = cumulative_oos_return - 1
        logger.info(f"[OOS_CUMULATIVE] 累积OOS收益率: {total_oos_return:.2%}")

        # 计算年化收益率（假设每个OOS窗口是6个月）
        total_years = len(successful_results) * (self.oos_window_months / 12)
        annualized_return = (
            ((cumulative_oos_return) ** (1 / total_years) - 1) if total_years > 0 else 0
        )
        logger.info(f"[OOS_ANNUALIZED] 年化OOS收益率: {annualized_return:.2%}")

    def _analyze_parameter_stability(self, successful_results: List[WFAResult]):
        """分析参数稳定性"""
        logger.info("[ANALYZE] 分析参数稳定性...")

        if len(successful_results) < 2:
            logger.warning("[WARNING] 成功结果不足2个，无法分析参数稳定性")
            return

        # 收集所有参数
        all_buy_params = {}
        all_sell_params = {}

        for result in successful_results:
            if result.best_params:
                # 收集buy参数
                if "buy_params" in result.best_params:
                    for param_name, param_value in result.best_params["buy_params"].items():
                        if param_name not in all_buy_params:
                            all_buy_params[param_name] = []
                        all_buy_params[param_name].append(param_value)

                # 收集sell参数
                if "sell_params" in result.best_params:
                    for param_name, param_value in result.best_params["sell_params"].items():
                        if param_name not in all_sell_params:
                            all_sell_params[param_name] = []
                        all_sell_params[param_name].append(param_value)

        # 分析参数稳定性
        def analyze_param_stability(param_dict, param_type):
            logger.info(f"[STABILITY] {param_type} 参数稳定性:")

            for param_name, values in param_dict.items():
                if len(values) > 1:
                    mean_val = np.mean(values)
                    std_val = np.std(values)
                    min_val = np.min(values)
                    max_val = np.max(values)
                    cv = std_val / mean_val if mean_val != 0 else float("inf")  # 变异系数

                    logger.info(
                        f"  {param_name}: 均值={mean_val:.4f}, 标准差={std_val:.4f}, CV={cv:.4f}, 范围=[{min_val:.4f}, {max_val:.4f}]"
                    )

                    if cv < 0.1:
                        logger.info(f"    ✅ 参数 {param_name} 非常稳定 (CV < 0.1)")
                    elif cv < 0.3:
                        logger.info(f"    ⚠️  参数 {param_name} 相对稳定 (0.1 <= CV < 0.3)")
                    else:
                        logger.info(f"    ❌ 参数 {param_name} 不稳定 (CV >= 0.3)")

        analyze_param_stability(all_buy_params, "BUY")
        analyze_param_stability(all_sell_params, "SELL")

    def _analyze_market_conditions(self, successful_results: List[WFAResult]):
        """分析不同市场条件下的表现"""
        logger.info("[ANALYZE] 分析市场条件适应性...")

        # 按时间段分类分析
        bull_market_results = []  # 牛市
        bear_market_results = []  # 熊市
        sideways_market_results = []  # 震荡市

        for result in successful_results:
            if result.oos_performance:
                market_change = result.oos_performance.get("market_change", 0)

                # 简单的市场分类（可以根据需要调整）
                if market_change > 0.05:  # 市场上涨超过5%
                    bull_market_results.append(result)
                elif market_change < -0.05:  # 市场下跌超过5%
                    bear_market_results.append(result)
                else:  # 市场变化在-5%到5%之间
                    sideways_market_results.append(result)

        def analyze_market_performance(results, market_type):
            if not results:
                logger.info(f"[MARKET] {market_type}: 无数据")
                return

            profits = [r.oos_performance["profit_total"] for r in results]
            sharpes = [r.oos_performance["sharpe"] for r in results]

            avg_profit = np.mean(profits)
            avg_sharpe = np.mean(sharpes)
            positive_ratio = sum(1 for p in profits if p > 0) / len(profits)

            logger.info(f"[MARKET] {market_type} ({len(results)} 个窗口):")
            logger.info(f"  平均收益率: {avg_profit:.2%}")
            logger.info(f"  平均Sharpe: {avg_sharpe:.3f}")
            logger.info(f"  正收益比例: {positive_ratio:.1%}")

        analyze_market_performance(bull_market_results, "牛市")
        analyze_market_performance(bear_market_results, "熊市")
        analyze_market_performance(sideways_market_results, "震荡市")

    def _save_detailed_results(self):
        """保存详细的WFA结果"""
        try:
            # 准备保存数据
            wfa_data = {
                "analysis_info": {
                    "strategy_name": self.strategy_name,
                    "analysis_time": datetime.now().isoformat(),
                    "is_window_months": self.is_window_months,
                    "oos_window_months": self.oos_window_months,
                    "roll_step_months": self.roll_step_months,
                    "start_date": self.start_date,
                    "end_date": self.end_date,
                    "total_windows": len(self.wfa_results),
                },
                "window_results": [],
                "combined_oos_trades": self.combined_oos_trades,
            }

            # 转换结果为可序列化格式
            for result in self.wfa_results:
                window_data = {
                    "window_id": result.window.window_id,
                    "is_timerange": result.window.get_is_timerange(),
                    "oos_timerange": result.window.get_oos_timerange(),
                    "is_optimization_success": result.is_optimization_success,
                    "oos_backtest_success": result.oos_backtest_success,
                    "best_params": result.best_params,
                    "is_performance": result.is_performance,
                    "oos_performance": result.oos_performance,
                    "error_message": result.error_message,
                }
                wfa_data["window_results"].append(window_data)

            # 保存JSON文件
            output_file = f"wfa_results_{self.strategy_name}_{current_time}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(wfa_data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"[SAVE] 详细结果已保存到: {output_file}")

            # 保存CSV摘要
            self._save_csv_summary()

        except Exception as e:
            logger.error(f"[ERROR] 保存结果失败: {e}")

    def _save_csv_summary(self):
        """保存CSV格式的摘要"""
        try:
            # 窗口摘要
            window_summary = []
            for result in self.wfa_results:
                row = {
                    "窗口ID": result.window.window_id,
                    "IS时间段": result.window.get_is_timerange(),
                    "OOS时间段": result.window.get_oos_timerange(),
                    "IS优化成功": "是" if result.is_optimization_success else "否",
                    "OOS回测成功": "是" if result.oos_backtest_success else "否",
                }

                # 添加IS性能指标
                if result.is_performance:
                    row.update(
                        {
                            "IS收益率": f"{result.is_performance.get('profit_total', 0):.2%}",
                            "IS_Sharpe": f"{result.is_performance.get('sharpe', 0):.3f}",
                            "IS交易次数": result.is_performance.get("total_trades", 0),
                            "IS胜率": f"{result.is_performance.get('win_rate', 0):.1%}",
                        }
                    )
                else:
                    row.update(
                        {
                            "IS收益率": "-",
                            "IS_Sharpe": "-",
                            "IS交易次数": "-",
                            "IS胜率": "-",
                        }
                    )

                # 添加OOS性能指标
                if result.oos_performance:
                    row.update(
                        {
                            "OOS收益率": f"{result.oos_performance.get('profit_total', 0):.2%}",
                            "OOS_Sharpe": f"{result.oos_performance.get('sharpe', 0):.3f}",
                            "OOS交易次数": result.oos_performance.get("total_trades", 0),
                            "OOS胜率": f"{result.oos_performance.get('win_rate', 0):.1%}",
                            "OOS最大回撤": f"{abs(result.oos_performance.get('max_drawdown', 0)):.2%}",
                            "OOS盈利因子": f"{result.oos_performance.get('profit_factor', 0):.2f}",
                            "OOS年化收益": f"{result.oos_performance.get('cagr', 0):.2%}",
                            "市场变化": f"{result.oos_performance.get('market_change', 0):.2%}",
                        }
                    )
                else:
                    row.update(
                        {
                            "OOS收益率": "-",
                            "OOS_Sharpe": "-",
                            "OOS交易次数": "-",
                            "OOS胜率": "-",
                            "OOS最大回撤": "-",
                            "OOS盈利因子": "-",
                            "OOS年化收益": "-",
                            "市场变化": "-",
                        }
                    )

                # 错误信息
                row["错误信息"] = result.error_message if result.error_message else ""

                window_summary.append(row)

            # 保存窗口摘要CSV
            df_windows = pd.DataFrame(window_summary)
            windows_csv = f"wfa_windows_summary_{self.strategy_name}_{current_time}.csv"
            df_windows.to_csv(windows_csv, index=False, encoding="utf-8-sig")

            logger.info(f"[SAVE] 窗口摘要已保存到: {windows_csv}")

            # 如果有交易记录，也保存交易CSV
            if self.combined_oos_trades:
                trades_csv = f"wfa_oos_trades_{self.strategy_name}_{current_time}.csv"
                df_trades = pd.DataFrame(self.combined_oos_trades)
                df_trades.to_csv(trades_csv, index=False, encoding="utf-8-sig")
                logger.info(f"[SAVE] OOS交易记录已保存到: {trades_csv}")

        except Exception as e:
            logger.error(f"[ERROR] 保存CSV摘要失败: {e}")

    def _generate_wfa_report(self):
        """生成WFA分析报告"""
        logger.info("\n" + "=" * 100)
        logger.info("🎯 前向分析 (Walk-Forward Analysis) 最终报告")
        logger.info("=" * 100)

        # 基础统计
        total_windows = len(self.wfa_results)
        successful_windows = [
            r for r in self.wfa_results if r.oos_backtest_success and r.oos_performance
        ]

        logger.info(f"\n📊 基础统计:")
        logger.info(f"  策略名称: {self.strategy_name}")
        logger.info(f"  分析时间段: {self.start_date} - {self.end_date}")
        logger.info(f"  总窗口数: {total_windows}")
        logger.info(f"  成功窗口数: {len(successful_windows)}")
        logger.info(f"  成功率: {len(successful_windows) / total_windows * 100:.1f}%")

        if not successful_windows:
            logger.warning("⚠️ 没有成功的WFA窗口，无法生成详细报告")
            return

        # OOS性能统计
        oos_profits = [r.oos_performance["profit_total"] for r in successful_windows]
        oos_sharpes = [r.oos_performance["sharpe"] for r in successful_windows]
        oos_dds = [abs(r.oos_performance["max_drawdown"]) for r in successful_windows]

        positive_windows = sum(1 for p in oos_profits if p > 0)

        logger.info(f"\n📈 样本外 (OOS) 性能评估:")
        logger.info(
            f"  正收益窗口: {positive_windows}/{len(successful_windows)} ({positive_windows / len(successful_windows) * 100:.1f}%)"
        )
        logger.info(f"  平均收益率: {np.mean(oos_profits):.2%} ± {np.std(oos_profits):.2%}")
        logger.info(f"  收益率中位数: {np.median(oos_profits):.2%}")
        logger.info(f"  收益率范围: [{np.min(oos_profits):.2%}, {np.max(oos_profits):.2%}]")
        logger.info(f"  平均Sharpe比率: {np.mean(oos_sharpes):.3f}")
        logger.info(f"  平均最大回撤: {np.mean(oos_dds):.2%}")

        # 累积性能
        cumulative_return = 1.0
        for profit in oos_profits:
            cumulative_return *= 1 + profit

        total_return = cumulative_return - 1
        total_years = len(successful_windows) * (self.oos_window_months / 12)
        annualized_return = ((cumulative_return) ** (1 / total_years) - 1) if total_years > 0 else 0

        logger.info(f"\n🎯 累积OOS表现:")
        logger.info(f"  累积收益率: {total_return:.2%}")
        logger.info(f"  年化收益率: {annualized_return:.2%}")
        logger.info(f"  分析年数: {total_years:.1f} 年")

        # 一致性分析
        consistent_positive = all(p > 0 for p in oos_profits)
        consistent_negative = all(p < 0 for p in oos_profits)

        logger.info(f"\n🔄 一致性评估:")
        if consistent_positive:
            logger.info("  ✅ 策略在所有OOS窗口中都实现正收益 - 高度一致")
        elif consistent_negative:
            logger.info("  ❌ 策略在所有OOS窗口中都产生亏损 - 一致性差")
        else:
            logger.info(f"  ⚠️ 策略收益有波动 - 需要关注风险管理")

        # 风险评估
        max_loss = min(oos_profits) if oos_profits else 0
        max_gain = max(oos_profits) if oos_profits else 0

        logger.info(f"\n⚠️ 风险评估:")
        logger.info(f"  单期最大亏损: {max_loss:.2%}")
        logger.info(f"  单期最大收益: {max_gain:.2%}")
        logger.info(f"  收益波动率: {np.std(oos_profits):.2%}")

        # 最终建议
        logger.info(f"\n💡 最终评估:")

        if positive_windows / len(successful_windows) >= 0.7 and np.mean(oos_profits) > 0.02:
            logger.info("  🎉 策略表现优秀：高胜率且平均收益良好")
        elif positive_windows / len(successful_windows) >= 0.6 and np.mean(oos_profits) > 0:
            logger.info("  ✅ 策略表现良好：胜率和收益都可接受")
        elif np.mean(oos_profits) > 0:
            logger.info("  ⚠️ 策略表现一般：平均收益为正但波动较大")
        else:
            logger.info("  ❌ 策略表现不佳：平均收益为负，需要优化")

        logger.info(f"\n📁 输出文件:")
        logger.info(f"  详细日志: {log_filename}")
        logger.info(f"  JSON结果: wfa_results_{self.strategy_name}_{current_time}.json")
        logger.info(f"  CSV摘要: wfa_windows_summary_{self.strategy_name}_{current_time}.csv")
        if self.combined_oos_trades:
            logger.info(f"  交易记录: wfa_oos_trades_{self.strategy_name}_{current_time}.csv")

        logger.info("=" * 100)


def load_wfa_config(config_file: str = "wfa_config.json") -> Dict[str, Any]:
    """加载WFA配置文件"""
    try:
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info(f"[CONFIG] 已加载配置文件: {config_file}")
            return config
        else:
            logger.warning(f"[CONFIG] 配置文件不存在，使用默认配置: {config_file}")
            return {}
    except Exception as e:
        logger.error(f"[ERROR] 读取配置文件失败: {e}")
        return {}


def main():
    """主函数"""
    print("🔍 前向分析 (Walk-Forward Analysis) 策略评测器")
    print("=" * 80)
    print(f"📝 日志文件: {log_filename}")
    print("=" * 80)

    # 加载配置文件
    config = load_wfa_config()

    # 策略配置（优先使用配置文件，否则使用默认值）
    strategy_config = config.get("strategy_config", {})
    strategy_name = strategy_config.get("strategy_name", "Strategy_Simple_Indicator_Test")
    config_path = strategy_config.get("config_path", "./user_data/config.json")

    # WFA参数配置
    wfa_params = config.get("wfa_parameters", {})
    wfa_config = {
        "is_window_months": wfa_params.get("is_window_months", 24),
        "oos_window_months": wfa_params.get("oos_window_months", 6),
        "roll_step_months": wfa_params.get("roll_step_months", 6),
        "start_date": wfa_params.get("start_date", "20220101"),
        "end_date": wfa_params.get("end_date", "20241201"),
        "timeframe": strategy_config.get("timeframe", "30m"),
    }

    print(f"🎯 策略: {strategy_name}")
    print(f"⏰ IS窗口: {wfa_config['is_window_months']}个月")
    print(f"📊 OOS窗口: {wfa_config['oos_window_months']}个月")
    print(f"🔄 滚动步长: {wfa_config['roll_step_months']}个月")
    print(f"📅 分析期间: {wfa_config['start_date']} - {wfa_config['end_date']}")
    print("=" * 80)

    # 检查配置文件
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        return

    try:
        # 创建WFA评测器
        evaluator = WFAStrategyEvaluator(
            strategy_name=strategy_name, config_path=config_path, **wfa_config
        )

        # 获取优化设置
        optimization_config = config.get("optimization_settings", {})

        # 显示优化配置
        print(f"⚙️ 优化设置:")
        print(f"  - 优化轮数: {optimization_config.get('hyperopt_epochs', 300)}")
        print(f"  - 最少交易: {optimization_config.get('hyperopt_min_trades', 50)}")
        print(f"  - 损失函数: {optimization_config.get('hyperopt_loss', 'SharpeHyperOptLoss')}")
        print(f"  - 优化空间: {optimization_config.get('spaces', ['buy', 'sell'])}")
        print("=" * 80)

        # 运行WFA分析
        results = evaluator.run_wfa_analysis(optimization_config)

        if results:
            print(f"\n✅ WFA分析完成！")
            print(f"📊 总窗口数: {len(results)}")
            print(f"🎯 成功窗口数: {len([r for r in results if r.oos_backtest_success])}")
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
