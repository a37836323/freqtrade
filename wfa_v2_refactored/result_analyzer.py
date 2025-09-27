#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
结果分析模块
负责WFA结果的统计分析和报告生成
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


try:
    from .data_types import WFAConfig, WFAResult
except ImportError:
    from data_types import WFAConfig, WFAResult


logger = logging.getLogger(__name__)


class ResultAnalyzer:
    """结果分析器"""

    def __init__(self, config: WFAConfig):
        self.config = config
        self.current_time = datetime.now().strftime("%Y%m%d_%H%M%S")

    def analyze_results(self, results: list[WFAResult]) -> dict[str, Any]:
        """分析WFA结果"""
        logger.info("[ANALYZE] 开始分析WFA结果...")

        # 基础统计
        analysis = self._basic_statistics(results)

        # 成功的窗口
        successful_windows = [
            r
            for r in results
            if r.optimization_success and r.oos_backtest_success and r.oos_performance
        ]

        if successful_windows:
            analysis.update(self._oos_performance_analysis(successful_windows))
            analysis.update(self._parameter_stability_analysis(successful_windows))

        return analysis

    def _basic_statistics(self, results: list[WFAResult]) -> dict[str, Any]:
        """基础统计分析"""
        total_windows = len(results)
        optimization_success_count = sum(1 for r in results if r.optimization_success)
        oos_success_count = sum(1 for r in results if r.oos_backtest_success)
        complete_success_count = sum(
            1 for r in results if r.optimization_success and r.oos_backtest_success
        )

        stats = {
            "total_windows": total_windows,
            "optimization_success_count": optimization_success_count,
            "oos_success_count": oos_success_count,
            "complete_success_count": complete_success_count,
            "optimization_success_rate": optimization_success_count / total_windows
            if total_windows > 0
            else 0,
            "oos_success_rate": oos_success_count / total_windows if total_windows > 0 else 0,
            "complete_success_rate": complete_success_count / total_windows
            if total_windows > 0
            else 0,
        }

        logger.info(f"[STATS] 总窗口数: {total_windows}")
        logger.info(
            f"[STATS] IS优化成功: {optimization_success_count}/{total_windows} ({stats['optimization_success_rate']:.1%})"
        )
        logger.info(
            f"[STATS] OOS回测成功: {oos_success_count}/{total_windows} ({stats['oos_success_rate']:.1%})"
        )
        logger.info(
            f"[STATS] 完整成功: {complete_success_count}/{total_windows} ({stats['complete_success_rate']:.1%})"
        )

        return stats

    def _oos_performance_analysis(self, successful_results: list[WFAResult]) -> dict[str, Any]:
        """OOS性能分析"""
        logger.info("[ANALYZE] 分析OOS样本外性能...")

        oos_profits = [r.oos_performance["profit_total"] for r in successful_results]
        oos_sharpes = [r.oos_performance["sharpe"] for r in successful_results]
        oos_win_rates = [r.oos_performance["win_rate"] for r in successful_results]

        positive_windows = sum(1 for p in oos_profits if p > 0)

        # 计算累积收益
        cumulative_return = 1.0
        for profit in oos_profits:
            cumulative_return *= 1 + profit
        total_return = cumulative_return - 1

        oos_analysis = {
            "oos_profits": oos_profits,
            "oos_sharpes": oos_sharpes,
            "oos_win_rates": oos_win_rates,
            "positive_windows": positive_windows,
            "positive_window_rate": positive_windows / len(successful_results),
            "avg_profit": np.mean(oos_profits),
            "std_profit": np.std(oos_profits),
            "median_profit": np.median(oos_profits),
            "min_profit": np.min(oos_profits),
            "max_profit": np.max(oos_profits),
            "avg_sharpe": np.mean(oos_sharpes),
            "avg_win_rate": np.mean(oos_win_rates),
            "cumulative_return": total_return,
        }

        logger.info(f"[OOS_PERFORMANCE] 基于 {len(successful_results)} 个成功窗口的统计:")
        logger.info(
            f"  正收益窗口: {positive_windows}/{len(successful_results)} ({oos_analysis['positive_window_rate']:.1%})"
        )
        logger.info(
            f"  平均收益率: {oos_analysis['avg_profit']:.2%} ± {oos_analysis['std_profit']:.2%}"
        )
        logger.info(f"  收益率中位数: {oos_analysis['median_profit']:.2%}")
        logger.info(f"  平均Sharpe: {oos_analysis['avg_sharpe']:.3f}")
        logger.info(f"  平均胜率: {oos_analysis['avg_win_rate']:.1%}")
        logger.info(f"[OOS_CUMULATIVE] 累积OOS收益率: {total_return:.2%}")

        return oos_analysis

    def _parameter_stability_analysis(self, successful_results: list[WFAResult]) -> dict[str, Any]:
        """参数稳定性分析"""
        logger.info("[ANALYZE] 分析参数稳定性...")

        if len(successful_results) < 2:
            logger.warning("[WARNING] 成功结果不足2个，无法分析参数稳定性")
            return {}

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

        # 分析稳定性
        buy_stability = self._analyze_param_stability(all_buy_params, "BUY")
        sell_stability = self._analyze_param_stability(all_sell_params, "SELL")

        return {
            "buy_param_stability": buy_stability,
            "sell_param_stability": sell_stability,
        }

    def _analyze_param_stability(
        self, param_dict: dict[str, list], param_type: str
    ) -> dict[str, dict]:
        """分析参数稳定性"""
        logger.info(f"[STABILITY] {param_type} 参数稳定性:")

        stability_results = {}

        for param_name, values in param_dict.items():
            if len(values) > 1:
                if isinstance(values[0], str):
                    # 分类参数
                    unique_values = set(values)
                    stability_results[param_name] = {
                        "type": "categorical",
                        "unique_count": len(unique_values),
                        "unique_values": list(unique_values),
                        "most_common": max(unique_values, key=values.count),
                    }
                    logger.info(f"  {param_name}: {len(unique_values)} 个不同取值 {unique_values}")
                else:
                    # 数值参数
                    mean_val = np.mean(values)
                    std_val = np.std(values)
                    min_val = np.min(values)
                    max_val = np.max(values)
                    cv = std_val / mean_val if mean_val != 0 else float("inf")

                    stability_level = "高" if cv < 0.1 else "中" if cv < 0.3 else "低"

                    stability_results[param_name] = {
                        "type": "numeric",
                        "mean": mean_val,
                        "std": std_val,
                        "cv": cv,
                        "min": min_val,
                        "max": max_val,
                        "stability_level": stability_level,
                    }

                    logger.info(
                        f"  {param_name}: 均值={mean_val:.4f}, 标准差={std_val:.4f}, CV={cv:.4f}, 范围=[{min_val:.4f}, {max_val:.4f}]"
                    )

                    if cv < 0.1:
                        logger.info(f"    ✅ 参数 {param_name} 非常稳定 (CV < 0.1)")
                    elif cv < 0.3:
                        logger.info(f"    ⚠️  参数 {param_name} 相对稳定 (0.1 <= CV < 0.3)")
                    else:
                        logger.info(f"    ❌ 参数 {param_name} 不稳定 (CV >= 0.3)")

        return stability_results

    def save_results(self, results: list[WFAResult], analysis: dict[str, Any]):
        """保存结果"""
        # 保存JSON详细结果
        self._save_json_results(results, analysis)

        # 保存CSV摘要
        self._save_csv_summary(results)

        # 生成最终报告
        self._generate_final_report(analysis)

    def _save_json_results(self, results: list[WFAResult], analysis: dict[str, Any]):
        """保存JSON格式详细结果"""
        try:
            wfa_data = {
                "analysis_info": {
                    "strategy_name": self.config.strategy_name,
                    "analysis_time": datetime.now().isoformat(),
                    "optimization_method": self.config.optimization_method,
                    "max_param_combinations": self.config.max_param_combinations,
                    "is_window_months": self.config.is_window_months,
                    "oos_window_months": self.config.oos_window_months,
                    "roll_step_months": self.config.roll_step_months,
                    "start_date": self.config.start_date,
                    "end_date": self.config.end_date,
                    "total_windows": len(results),
                },
                "analysis_summary": analysis,
                "window_results": [],
            }

            # 转换结果为可序列化格式
            for result in results:
                window_data = {
                    "window_id": result.window.window_id,
                    "is_timerange": result.window.get_is_timerange(),
                    "oos_timerange": result.window.get_oos_timerange(),
                    "optimization_success": result.optimization_success,
                    "oos_backtest_success": result.oos_backtest_success,
                    "best_params": result.best_params,
                    "is_best_performance": result.is_best_performance,
                    "oos_performance": result.oos_performance,
                    "error_message": result.error_message,
                    "is_results_count": len(result.is_results),
                    "is_successful_count": len([r for r in result.is_results if r.success]),
                }
                wfa_data["window_results"].append(window_data)

            # 保存JSON文件
            output_file = (
                f"wfa_results_refactored_{self.config.strategy_name}_{self.current_time}.json"
            )
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(wfa_data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"[SAVE] 详细结果已保存到: {output_file}")

        except Exception as e:
            logger.error(f"[ERROR] 保存JSON结果失败: {e}")

    def _save_csv_summary(self, results: list[WFAResult]):
        """保存CSV格式摘要"""
        try:
            window_summary = []
            for result in results:
                row = {
                    "窗口ID": result.window.window_id,
                    "IS时间段": result.window.get_is_timerange(),
                    "OOS时间段": result.window.get_oos_timerange(),
                    "IS优化成功": "是" if result.optimization_success else "否",
                    "OOS回测成功": "是" if result.oos_backtest_success else "否",
                    "IS参数测试数": len(result.is_results),
                    "IS成功测试数": len([r for r in result.is_results if r.success]),
                }

                # 添加IS最佳性能
                if result.is_best_performance:
                    row.update(
                        {
                            "IS最佳收益率": f"{result.is_best_performance.get('profit_total', 0):.2%}",
                            "IS最佳Sharpe": f"{result.is_best_performance.get('sharpe', 0):.3f}",
                            "IS交易次数": result.is_best_performance.get("total_trades", 0),
                            "IS胜率": f"{result.is_best_performance.get('win_rate', 0):.1%}",
                        }
                    )
                else:
                    row.update(
                        {
                            "IS最佳收益率": "-",
                            "IS最佳Sharpe": "-",
                            "IS交易次数": "-",
                            "IS胜率": "-",
                        }
                    )

                # 添加OOS性能
                if result.oos_performance:
                    row.update(
                        {
                            "OOS收益率": f"{result.oos_performance.get('profit_total', 0):.2%}",
                            "OOS_Sharpe": f"{result.oos_performance.get('sharpe', 0):.3f}",
                            "OOS交易次数": result.oos_performance.get("total_trades", 0),
                            "OOS胜率": f"{result.oos_performance.get('win_rate', 0):.1%}",
                            "OOS最大回撤": f"{abs(result.oos_performance.get('max_drawdown', 0)):.2%}",
                            "OOS盈利因子": f"{result.oos_performance.get('profit_factor', 0):.2f}",
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
                        }
                    )

                row["错误信息"] = result.error_message if result.error_message else ""
                window_summary.append(row)

            # 保存窗口摘要CSV
            df_windows = pd.DataFrame(window_summary)
            windows_csv = f"wfa_windows_summary_refactored_{self.config.strategy_name}_{self.current_time}.csv"
            df_windows.to_csv(windows_csv, index=False, encoding="utf-8-sig")

            logger.info(f"[SAVE] 窗口摘要已保存到: {windows_csv}")

        except Exception as e:
            logger.error(f"[ERROR] 保存CSV摘要失败: {e}")

    def _generate_final_report(self, analysis: dict[str, Any]):
        """生成最终报告"""
        logger.info("\n" + "=" * 100)
        logger.info("🎯 前向分析 (Walk-Forward Analysis) 重构版本 最终报告")
        logger.info("=" * 100)

        # 基础统计
        logger.info(f"\n📊 基础统计:")
        logger.info(f"  策略名称: {self.config.strategy_name}")
        logger.info(f"  优化方法: {self.config.optimization_method}")
        logger.info(f"  参数组合数: {self.config.max_param_combinations}")
        logger.info(f"  分析时间段: {self.config.start_date} - {self.config.end_date}")
        logger.info(f"  总窗口数: {analysis['total_windows']}")
        logger.info(f"  成功窗口数: {analysis['complete_success_count']}")
        logger.info(f"  成功率: {analysis['complete_success_rate']:.1%}")

        if analysis.get("avg_profit") is not None:
            # OOS性能统计
            logger.info(f"\n📈 样本外 (OOS) 性能评估:")
            logger.info(
                f"  正收益窗口: {analysis['positive_windows']}/{analysis['complete_success_count']} ({analysis['positive_window_rate']:.1%})"
            )
            logger.info(
                f"  平均收益率: {analysis['avg_profit']:.2%} ± {analysis['std_profit']:.2%}"
            )
            logger.info(f"  收益率中位数: {analysis['median_profit']:.2%}")
            logger.info(
                f"  收益率范围: [{analysis['min_profit']:.2%}, {analysis['max_profit']:.2%}]"
            )

            # 累积性能
            logger.info(f"\n🎯 累积OOS表现:")
            logger.info(f"  累积收益率: {analysis['cumulative_return']:.2%}")

            # 最终评估
            logger.info(f"\n💡 最终评估:")
            if analysis["positive_window_rate"] >= 0.7 and analysis["avg_profit"] > 0.02:
                logger.info("  🎉 策略表现优秀：高胜率且平均收益良好")
            elif analysis["positive_window_rate"] >= 0.6 and analysis["avg_profit"] > 0:
                logger.info("  ✅ 策略表现良好：胜率和收益都可接受")
            elif analysis["avg_profit"] > 0:
                logger.info("  ⚠️ 策略表现一般：平均收益为正但波动较大")
            else:
                logger.info("  ❌ 策略表现不佳：平均收益为负，需要优化")
        else:
            logger.warning("⚠️ 没有成功的WFA窗口，无法生成详细报告")

        logger.info(f"\n📁 输出文件:")
        logger.info(
            f"  JSON结果: wfa_results_refactored_{self.config.strategy_name}_{self.current_time}.json"
        )
        logger.info(
            f"  CSV摘要: wfa_windows_summary_refactored_{self.config.strategy_name}_{self.current_time}.csv"
        )

        logger.info("=" * 100)
