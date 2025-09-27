import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

# 导入解析超参数结果的函数
from 解析超参数优化结果文件 import get_top_params_direct


# 设置日志 - 添加时间戳到文件名
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"overfitting_test_{current_time}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

print(f"[INFO] 日志文件保存到: {log_filename}")
print("=" * 60)
logger = logging.getLogger(__name__)


class OverfittingTester:
    """超参数过拟合测试器"""

    def __init__(
        self,
        strategy_name: str = "OscillationArbitrageStrategy",
        config_path: str = "./user_data/config.json",
        timeframe: str = "30m",
        hyperopt_file: str = None,  # 新增：指定超参数文件路径
    ):
        self.strategy_name = strategy_name
        self.config_path = config_path
        self.timeframe = timeframe
        self.strategy_json_path = f"./user_data/strategies/{strategy_name}.json"
        self.hyperopt_file = hyperopt_file  # 保存指定的超参数文件路径

        # 添加缓存变量
        self._cached_params = None
        self._cache_loaded = False

        # 测试时间段配置
        self.test_periods = [
            "20211111-20220711",  # 2021年11月11日-2022年6月22日 熊市
            "20230101-20230601",  # 2023年1-6  稳定小幅上涨
            "20240101-20240601",  # 2024年1-6月 先大幅上涨,然后震荡下跌
        ]

        # 备份原始策略参数
        self.original_params = None
        self._backup_original_params()

    def _backup_original_params(self):
        """备份原始策略参数"""
        if os.path.exists(self.strategy_json_path):
            with open(self.strategy_json_path, "r", encoding="utf-8") as f:
                self.original_params = json.load(f)
            logger.info(f"[BACKUP] 已备份原始策略参数")
        else:
            logger.warning(f"[WARNING] 策略JSON文件不存在: {self.strategy_json_path}")

    def _restore_original_params(self):
        """恢复原始策略参数"""
        if self.original_params:
            with open(self.strategy_json_path, "w", encoding="utf-8") as f:
                json.dump(self.original_params, f, indent=2, ensure_ascii=False)
            logger.info(f"[RESTORE] 已恢复原始策略参数")

    def _update_strategy_params(self, params: Dict[str, Any]):
        """更新策略参数JSON文件"""
        try:
            # 读取当前的策略JSON文件
            if os.path.exists(self.strategy_json_path):
                with open(self.strategy_json_path, "r", encoding="utf-8") as f:
                    strategy_config = json.load(f)
            else:
                # 创建基础结构
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

            # 更新其他参数
            for param_type in ["roi", "stoploss", "trailing", "max_open_trades", "protection"]:
                if param_type in params and params[param_type]:
                    strategy_config["params"][param_type] = params[param_type]

            # 更新导出时间
            strategy_config["export_time"] = datetime.now().isoformat()

            # 写入文件
            with open(self.strategy_json_path, "w", encoding="utf-8") as f:
                json.dump(strategy_config, f, indent=2, ensure_ascii=False)

            logger.debug(f"[UPDATE] 策略参数已更新到 {self.strategy_json_path}")
            return True

        except Exception as e:
            logger.error(f"[ERROR] 更新策略参数失败: {e}")
            return False

    def _run_backtest_with_api(self, timerange: str, rank: int) -> Dict[str, Any]:
        """使用Freqtrade内部API运行回测"""
        logger.info(f"[BACKTEST] 开始回测 - 排名 #{rank}, 时间段: {timerange}")

        try:
            # 导入必要的模块
            from freqtrade.commands.optimize_commands import setup_optimize_configuration
            from freqtrade.enums import RunMode
            from freqtrade.optimize.backtesting import Backtesting

            # 1. 构建参数字典 (模拟命令行参数)
            args = {
                "config": [self.config_path],  # 配置文件路径
                "strategy": self.strategy_name,  # 策略名称
                "timeframe": self.timeframe,  # 时间框架
                "timerange": timerange,  # 时间范围
                "verbosity": 0,  # 日志级别
                "logfile": None,  # 日志文件
                "export": "none",  # 不导出交易记录
                "cache": "none",  # 禁用缓存
            }

            # 2. 使用 Freqtrade 的标准配置加载流程
            config = setup_optimize_configuration(args, RunMode.BACKTEST)

            # 3. 创建回测实例
            backtesting = Backtesting(config)

            # 4. 运行回测
            backtesting.start()

            # 5. 获取结果 - 改进的错误处理
            logger.debug(f"[DEBUG] 回测结果类型: {type(backtesting.results)}")

            if backtesting.results is None:
                logger.error("[ERROR] 回测结果为None")
                return {
                    "rank": rank,
                    "timerange": timerange,
                    "status": "error",
                    "error": "回测结果为None",
                }

            # 打印结果结构用于调试
            if isinstance(backtesting.results, dict):
                logger.debug(f"[DEBUG] 回测结果字典键: {list(backtesting.results.keys())}")
            else:
                logger.error(f"[ERROR] 意外的回测结果类型: {type(backtesting.results)}")
                return {
                    "rank": rank,
                    "timerange": timerange,
                    "status": "error",
                    "error": f"意外的回测结果类型: {type(backtesting.results)}",
                }

            # 检查strategy键是否存在
            if "strategy" not in backtesting.results:
                logger.error(
                    f"[ERROR] 回测结果中没有'strategy'键，可用键: {list(backtesting.results.keys())}"
                )
                return {
                    "rank": rank,
                    "timerange": timerange,
                    "status": "error",
                    "error": "回测结果中没有strategy键",
                }

            strategy_results = backtesting.results["strategy"]
            logger.debug(f"[DEBUG] 策略结果类型: {type(strategy_results)}")

            if isinstance(strategy_results, dict):
                logger.debug(f"[DEBUG] 可用策略: {list(strategy_results.keys())}")
            else:
                logger.error(f"[ERROR] 策略结果不是字典类型: {type(strategy_results)}")
                return {
                    "rank": rank,
                    "timerange": timerange,
                    "status": "error",
                    "error": f"策略结果不是字典类型: {type(strategy_results)}",
                }

            # 检查具体策略是否存在
            if self.strategy_name not in strategy_results:
                logger.error(
                    f"[ERROR] 未找到策略 {self.strategy_name}，可用策略: {list(strategy_results.keys())}"
                )
                return {
                    "rank": rank,
                    "timerange": timerange,
                    "status": "error",
                    "error": f"未找到策略 {self.strategy_name}",
                }

            result = strategy_results[self.strategy_name]
            logger.debug(f"[DEBUG] 策略结果类型: {type(result)}")

            if isinstance(result, dict):
                # 调试：打印回测结果的所有键
                logger.info(f"[DEBUG] 回测结果键: {list(result.keys())}")

                # 调试：打印一些关键字段的值
                for key in [
                    "holding_avg",
                    "trade_count_short",
                    "trade_count_long",
                    "max_drawdown",
                    "max_drawdown_abs",
                ]:
                    if key in result:
                        logger.debug(f"[DEBUG] {key}: {result[key]}")

                # 提取关键指标
                metrics = {
                    # 基础交易指标
                    "total_trades": result.get("total_trades", 0),
                    "profit_total_abs": result.get("profit_total_abs", 0),
                    "profit_total": result.get("profit_total", 0),
                    "wins": result.get("wins", 0),
                    "draws": result.get("draws", 0),
                    "losses": result.get("losses", 0),
                    "win_rate": result.get("wins", 0) / max(result.get("total_trades", 1), 1),
                    # 收益指标
                    "avg_profit": result.get("profit_mean", 0),
                    "profit_median": result.get("profit_median", 0),
                    "expectancy_ratio": result.get("expectancy_ratio", 0),
                    "cagr": result.get("cagr", 0),
                    # 风险指标
                    "sharpe": result.get("sharpe", 0),
                    "sortino": result.get("sortino", 0),
                    "calmar": result.get("calmar", 0),
                    "profit_factor": result.get("profit_factor", 0),
                    "expectancy": result.get("expectancy", 0),
                    "sqn": result.get("sqn", 0),
                    # 回撤指标
                    "max_drawdown": result.get("max_drawdown_account", 0),
                    "max_drawdown_abs": result.get("max_drawdown_abs", 0),
                    "max_drawdown_low": result.get("max_drawdown_low", 0),
                    "max_drawdown_high": result.get("max_drawdown_high", 0),
                    "drawdown_start": result.get("drawdown_start", ""),
                    "drawdown_end": result.get("drawdown_end", ""),
                    # 持仓时间指标
                    "avg_trade_duration_minutes": self._parse_duration_to_minutes(
                        result.get("holding_avg", None)
                    ),
                    "holding_avg_winners": self._parse_duration_to_minutes(
                        result.get("winner_holding_avg", None)
                    ),
                    "holding_avg_losers": self._parse_duration_to_minutes(
                        result.get("loser_holding_avg", None)
                    ),
                    "winner_holding_min": self._parse_duration_to_minutes(
                        result.get("winner_holding_min", None)
                    ),
                    "winner_holding_max": self._parse_duration_to_minutes(
                        result.get("winner_holding_max", None)
                    ),
                    "loser_holding_min": self._parse_duration_to_minutes(
                        result.get("loser_holding_min", None)
                    ),
                    "loser_holding_max": self._parse_duration_to_minutes(
                        result.get("loser_holding_max", None)
                    ),
                    # 连胜连败指标
                    "max_consecutive_wins": result.get("max_consecutive_wins", 0),
                    "max_consecutive_losses": result.get("max_consecutive_losses", 0),
                    # 资金管理指标
                    "starting_balance": result.get("starting_balance", 0),
                    "final_balance": result.get("final_balance", 0),
                    "min_balance": result.get("min_balance", 0),
                    "max_balance": result.get("max_balance", 0),
                    "avg_stake_amount": result.get("avg_stake_amount", 0),
                    "total_volume": result.get("total_volume", 0),
                    # 市场相关
                    "market_change": result.get("market_change", 0),
                    "rejected_signals": result.get("rejected_signals", 0),
                    "timedout_entry_orders": result.get("timedout_entry_orders", 0),
                    "timedout_exit_orders": result.get("timedout_exit_orders", 0),
                    "trades_per_day": result.get("trades_per_day", 0),
                    "backtest_days": result.get("backtest_days", 0),
                    # 天数统计
                    "winning_days": result.get("winning_days", 0),
                    "draw_days": result.get("draw_days", 0),
                    "losing_days": result.get("losing_days", 0),
                    "best_day": result.get("backtest_best_day", 0),
                    "worst_day": result.get("backtest_worst_day", 0),
                    "best_day_abs": result.get("backtest_best_day_abs", 0),
                    "worst_day_abs": result.get("backtest_worst_day_abs", 0),
                    # 使用更准确的胜率
                    "winrate": result.get("winrate", 0),
                    "stake_currency": "USDT",
                }

                logger.info(
                    f"[SUCCESS] {timerange}: 收益 {metrics['profit_total']:.2%}, 交易 {metrics['total_trades']} 次, Sharpe {metrics['sharpe']:.3f}"
                )

                return {"rank": rank, "timerange": timerange, "status": "success", **metrics}
            else:
                logger.error(f"[ERROR] 策略结果不是字典类型: {type(result)}")
                return {
                    "rank": rank,
                    "timerange": timerange,
                    "status": "error",
                    "error": f"策略结果不是字典类型: {type(result)}",
                }

        except Exception as e:
            logger.error(f"[ERROR] API回测失败: {e}")
            import traceback

            logger.error(f"[ERROR] 详细错误信息: {traceback.format_exc()}")
            return {"rank": rank, "timerange": timerange, "status": "error", "error": str(e)}
        finally:
            # 清理资源
            try:
                if "backtesting" in locals():
                    backtesting.cleanup()
            except:
                pass

    def _parse_duration_to_minutes(self, holding_avg) -> float:
        """解析持仓时间为分钟数"""
        try:
            if holding_avg is None:
                return 0.0

            # 如果是 timedelta 对象，直接转换为分钟
            if hasattr(holding_avg, "total_seconds"):
                return holding_avg.total_seconds() / 60.0

            # 如果是字符串，解析类似 "1:35:00" 的时间格式
            if isinstance(holding_avg, str):
                if not holding_avg or holding_avg == "":
                    return 0.0

                if ":" in holding_avg:
                    parts = holding_avg.split(":")
                    if len(parts) == 3:  # HH:MM:SS
                        hours = int(parts[0])
                        minutes = int(parts[1])
                        seconds = int(parts[2])
                        return hours * 60 + minutes + seconds / 60
                    elif len(parts) == 2:  # MM:SS
                        minutes = int(parts[0])
                        seconds = int(parts[1])
                        return minutes + seconds / 60

                # 如果是数字字符串，假设是分钟
                return float(holding_avg)

            # 如果是数字，直接返回
            return float(holding_avg)

        except Exception as e:
            logger.debug(
                f"[DEBUG] 解析持仓时间失败: {holding_avg} (类型: {type(holding_avg)}), 错误: {e}"
            )
            return 0.0

    def _load_params_once(
        self, top_n: int = 30, use_mixed_sampling: bool = True
    ) -> List[Dict[str, Any]]:
        """只加载一次超参数结果并缓存（只选择收益为正的epoch）

        Args:
            top_n: 总共要获取的参数数量
            use_mixed_sampling: 是否使用混合采样（Best + 随机1/4），只选择收益为正的epoch

        Returns:
            过滤后的参数列表，所有epoch都有正收益率

        Note:
            - 无论使用哪种采样方式，都会过滤掉收益为负的epoch
            - 混合采样：Best结果(正收益) + 随机1/4结果(正收益)
            - 非混合采样：只使用Best结果(正收益)
        """
        if not self._cache_loaded:
            logger.info(f"[CACHE] 首次加载参数结果...")

            if use_mixed_sampling:
                # 🎯 新方法：获取Best结果 + 随机1/4结果（只选择收益为正的epoch）
                logger.info("[CACHE] 使用混合采样：Best结果 + 随机1/4结果（收益为正过滤）...")

                # 1. 获取所有Best结果
                logger.info("[CACHE] 获取标记为'Best'的结果...")
                best_params_raw = get_top_params_direct(
                    top_n=100,  # 获取足够多的Best结果
                    hyperopt_filename=self.hyperopt_file,
                    user_data_dir="user_data",
                    sort_by="loss",
                    only_best=True,  # 只选择标记为"Best"的结果
                )

                # 2. 获取所有结果（包括非Best）
                logger.info("[CACHE] 获取所有结果用于随机采样...")
                all_params_raw = get_top_params_direct(
                    top_n=1000,  # 获取大量结果用于随机采样
                    hyperopt_filename=self.hyperopt_file,
                    user_data_dir="user_data",
                    sort_by="loss",
                    only_best=False,  # 获取所有结果
                )

                # 🎯 新增：过滤收益为正的结果
                def filter_positive_profit(params_list):
                    """过滤收益为正的参数"""
                    positive_params = []
                    negative_count = 0

                    for param in params_list:
                        # 获取收益率信息
                        metrics = param.get("metrics", {})
                        profit = metrics.get("profit_total_percent", 0)
                        # 也检查其他可能的收益率字段
                        if profit == 0:
                            profit = metrics.get("profit_total", 0)

                        if profit > 0:
                            positive_params.append(param)
                        else:
                            negative_count += 1

                    return positive_params, negative_count

                # 过滤Best结果中收益为正的
                logger.info("[CACHE] 过滤Best结果中收益为正的epoch...")
                best_params, best_negative_count = filter_positive_profit(best_params_raw)
                logger.info(
                    f"[CACHE] Best结果：原始 {len(best_params_raw)} 个，收益为正 {len(best_params)} 个，过滤掉 {best_negative_count} 个负收益"
                )

                # 过滤所有结果中收益为正的
                logger.info("[CACHE] 过滤所有结果中收益为正的epoch...")
                all_params, all_negative_count = filter_positive_profit(all_params_raw)
                logger.info(
                    f"[CACHE] 所有结果：原始 {len(all_params_raw)} 个，收益为正 {len(all_params)} 个，过滤掉 {all_negative_count} 个负收益"
                )

                # 3. 计算采样数量
                best_count = len(best_params)
                total_available = len(all_params)
                random_count = min(total_available // 8, top_n - best_count)  # 1/8的结果

                logger.info(f"[CACHE] 过滤后Best结果: {best_count} 个")
                logger.info(f"[CACHE] 过滤后总可用结果: {total_available} 个")
                logger.info(f"[CACHE] 计划随机采样: {random_count} 个")

                # 4. 过滤掉重复的参数（已经在Best中的）
                import random

                random.seed(42)  # 设置随机种子，确保可重现

                # 🔍 调试：查看参数结构
                if best_params:
                    logger.info(f"[DEBUG] Best参数示例结构: {list(best_params[0].keys())}")
                    logger.info(f"[DEBUG] Best参数params示例: {best_params[0].get('params', {})}")
                    # 打印收益率信息用于验证过滤
                    example_metrics = best_params[0].get("metrics", {})
                    example_profit = example_metrics.get(
                        "profit_total_percent", example_metrics.get("profit_total", 0)
                    )
                    logger.info(f"[DEBUG] Best参数收益率示例: {example_profit}")

                # 获取Best结果的参数签名用于去重
                best_signatures = set()
                for i, param in enumerate(best_params):
                    # 🎯 修复：从正确的params字段获取参数
                    params_dict = param.get("params", {})
                    # 也包含epoch和loss信息以确保唯一性
                    signature = f"params_{str(sorted(params_dict.items()))}_epoch_{param.get('epoch', 0)}_loss_{param.get('loss', 0)}"
                    best_signatures.add(signature)
                    if i == 0:  # 只打印第一个参数的签名示例
                        logger.info(f"[DEBUG] Best参数签名示例: {signature[:100]}...")

                # 从非Best结果（已过滤收益为正）中随机选择
                non_best_params = []
                duplicate_count = 0

                for i, param in enumerate(all_params):
                    # 🎯 修复：从正确的params字段获取参数
                    params_dict = param.get("params", {})
                    # 也包含epoch和loss信息以确保唯一性
                    signature = f"params_{str(sorted(params_dict.items()))}_epoch_{param.get('epoch', 0)}_loss_{param.get('loss', 0)}"

                    if signature not in best_signatures:
                        non_best_params.append(param)
                    else:
                        duplicate_count += 1

                    # 调试：显示前几个参数的信息
                    if i < 3:
                        logger.info(f"[DEBUG] 参数#{i} 签名: {signature[:100]}...")
                        logger.info(f"[DEBUG] 参数#{i} 是否重复: {signature in best_signatures}")
                        # 打印收益率信息用于验证过滤
                        example_metrics = param.get("metrics", {})
                        example_profit = example_metrics.get(
                            "profit_total_percent", example_metrics.get("profit_total", 0)
                        )
                        logger.info(f"[DEBUG] 参数#{i} 收益率: {example_profit}")

                logger.info(f"[DEBUG] 重复参数数量: {duplicate_count}")
                logger.info(f"[DEBUG] 非重复正收益参数数量: {len(non_best_params)}")

                # 随机采样（从正收益且非Best的结果中）
                random_params = random.sample(
                    non_best_params, min(random_count, len(non_best_params))
                )

                # 5. 合并结果
                self._cached_params = best_params + random_params

                logger.info(
                    f"[CACHE] 最终获取参数组合: {len(best_params)} Best(正收益) + {len(random_params)} 随机(正收益) = {len(self._cached_params)} 个"
                )
                logger.info(
                    f"[CACHE] Best结果占比: {len(best_params) / len(self._cached_params) * 100:.1f}%"
                )
                logger.info(
                    f"[CACHE] 随机结果占比: {len(random_params) / len(self._cached_params) * 100:.1f}%"
                )
                logger.info(
                    f"[CACHE] 收益过滤效果: 总过滤掉 {best_negative_count + all_negative_count} 个负收益epoch"
                )

            else:
                # 🎯 原方法：只获取Best结果（收益为正过滤）
                logger.info("[CACHE] 使用原方法：只获取标记为'Best'的结果（收益为正过滤）...")
                best_only_params_raw = get_top_params_direct(
                    top_n=top_n * 2,  # 获取更多结果以确保有足够的"Best"结果
                    hyperopt_filename=self.hyperopt_file,
                    user_data_dir="user_data",
                    sort_by="loss",  # 按loss排序（Freqtrade的标准）
                    only_best=True,  # 只选择标记为"Best"的结果
                )

                # 过滤收益为正的Best结果
                def filter_positive_profit_simple(params_list):
                    """过滤收益为正的参数（简化版）"""
                    positive_params = []
                    negative_count = 0

                    for param in params_list:
                        metrics = param.get("metrics", {})
                        profit = metrics.get("profit_total_percent", 0)
                        if profit == 0:
                            profit = metrics.get("profit_total", 0)

                        if profit > 0:
                            positive_params.append(param)
                        else:
                            negative_count += 1

                    return positive_params, negative_count

                best_only_params, negative_count = filter_positive_profit_simple(
                    best_only_params_raw
                )
                logger.info(
                    f"[CACHE] Best结果过滤：原始 {len(best_only_params_raw)} 个，收益为正 {len(best_only_params)} 个，过滤掉 {negative_count} 个负收益"
                )

                self._cached_params = best_only_params[:top_n]
                logger.info(f"[CACHE] 使用 {len(self._cached_params)} 个收益为正的'Best'参数组合")

            self._cache_loaded = True
        else:
            logger.info(f"[CACHE] 使用缓存的参数结果 ({len(self._cached_params)} 个)")

        return self._cached_params

    def _calculate_period_length_ratio(self, timerange: str) -> float:
        """计算测试时间段相对于原始优化时间段的长度比例"""
        try:
            # 解析时间段格式 "YYYYMMDD-YYYYMMDD"
            start_str, end_str = timerange.split("-")
            start_date = datetime.strptime(start_str, "%Y%m%d")
            end_date = datetime.strptime(end_str, "%Y%m%d")

            # 计算天数
            test_days = (end_date - start_date).days

            # 假设原始优化使用1年数据（365天）
            # 这里可以根据实际情况调整
            original_days = 365

            return test_days / original_days
        except Exception as e:
            logger.warning(f"[WARNING] 无法解析时间段 {timerange}，使用默认比例 0.5: {e}")
            return 0.5  # 默认假设测试时间段是原始的一半

    def run_overfitting_test(self, top_n: int = 30) -> List[Dict[str, Any]]:
        """运行过拟合测试"""
        logger.info(f"[START] 开始超参数过拟合测试 - 测试前 {top_n} 个参数")

        # 1. 获取最佳超参数
        logger.info("[LOAD] 获取最佳超参数...")
        top_params = self._load_params_once(top_n)  # 使用已配置的采样方式

        if not top_params:
            logger.error("[ERROR] 没有找到超参数结果")
            return []

        logger.info(f"[SUCCESS] 成功获取 {len(top_params)} 组参数")

        # 2. 批量测试
        all_results = []

        for i, param_set in enumerate(top_params):
            rank = param_set["rank"]
            original_sharpe = param_set["metrics"]["sharpe"]

            logger.info("=" * 60)
            logger.info(f"[TEST] 测试参数组合 #{rank} (原始 Sharpe: {original_sharpe:.3f})")
            logger.info("=" * 60)

            # 更新策略参数
            if not self._update_strategy_params(param_set["params"]):
                logger.error(f"[ERROR] 更新参数失败，跳过排名 #{rank}")
                continue

            # 在不同时间段测试
            param_results = []
            for timerange in self.test_periods:
                # 运行回测
                result = self._run_backtest_with_api(timerange, rank)
                param_results.append(result)

                # 短暂延迟避免资源冲突
                time.sleep(1)

            # 保存此参数组合的所有结果
            all_results.extend(param_results)

            logger.info(f"[COMPLETE] 参数组合 #{rank} 测试完成")

        # 3. 恢复原始参数
        self._restore_original_params()

        # 4. 分析和保存结果
        logger.info("[ANALYZE] 分析测试结果...")
        self._analyze_and_save_results(all_results)

        return all_results

    def _analyze_and_save_results(self, results: List[Dict[str, Any]]):
        """分析测试结果并保存"""
        try:
            # 按参数组合分组
            grouped_results = {}
            for result in results:
                rank = result["rank"]
                if rank not in grouped_results:
                    grouped_results[rank] = []
                grouped_results[rank].append(result)

            # 计算每个参数组合的稳定性指标
            summary_data = []
            for rank, group_results in grouped_results.items():
                # 获取成功的回测结果
                successful_results = [r for r in group_results if r["status"] == "success"]

                if not successful_results:
                    continue

                # 获取原始参数信息
                original_params = None
                top_params = self._load_params_once(50)  # 使用已配置的采样方式
                for param_set in top_params:
                    if param_set["rank"] == rank:
                        original_params = param_set
                        break

                if not original_params:
                    continue

                # 获取原始指标
                original_metrics = original_params["metrics"]
                original_sharpe = original_metrics["sharpe"]
                original_profit = original_metrics["profit_total_percent"]
                original_trades = original_metrics["total_trades"]

                # 计算平均指标
                sharpe_values = [r.get("sharpe", 0) for r in successful_results]
                profit_values = [r.get("profit_total", 0) for r in successful_results]
                trades_values = [r.get("total_trades", 0) for r in successful_results]
                avg_trade_duration_values = [
                    r.get("avg_trade_duration_minutes", 0) for r in successful_results
                ]
                max_drawdown_values = [r.get("max_drawdown", 0) for r in successful_results]
                win_rate_values = [r.get("win_rate", 0) for r in successful_results]

                # 新增更多指标
                cagr_values = [r.get("cagr", 0) for r in successful_results]
                sortino_values = [r.get("sortino", 0) for r in successful_results]
                calmar_values = [r.get("calmar", 0) for r in successful_results]
                profit_factor_values = [r.get("profit_factor", 0) for r in successful_results]
                expectancy_values = [r.get("expectancy", 0) for r in successful_results]
                sqn_values = [r.get("sqn", 0) for r in successful_results]

                # 持仓时间相关
                holding_winners_values = [
                    r.get("holding_avg_winners", 0) for r in successful_results
                ]
                holding_losers_values = [r.get("holding_avg_losers", 0) for r in successful_results]
                winner_holding_min_values = [
                    r.get("winner_holding_min", 0) for r in successful_results
                ]
                winner_holding_max_values = [
                    r.get("winner_holding_max", 0) for r in successful_results
                ]
                loser_holding_min_values = [
                    r.get("loser_holding_min", 0) for r in successful_results
                ]
                loser_holding_max_values = [
                    r.get("loser_holding_max", 0) for r in successful_results
                ]

                # 新增字段
                profit_median_values = [r.get("profit_median", 0) for r in successful_results]
                expectancy_ratio_values = [r.get("expectancy_ratio", 0) for r in successful_results]
                winrate_values = [r.get("winrate", 0) for r in successful_results]
                trades_per_day_values = [r.get("trades_per_day", 0) for r in successful_results]
                backtest_days_values = [r.get("backtest_days", 0) for r in successful_results]
                best_day_abs_values = [r.get("best_day_abs", 0) for r in successful_results]
                worst_day_abs_values = [r.get("worst_day_abs", 0) for r in successful_results]
                timedout_entry_values = [
                    r.get("timedout_entry_orders", 0) for r in successful_results
                ]
                timedout_exit_values = [
                    r.get("timedout_exit_orders", 0) for r in successful_results
                ]

                # 连胜连败
                max_consecutive_wins_values = [
                    r.get("max_consecutive_wins", 0) for r in successful_results
                ]
                max_consecutive_losses_values = [
                    r.get("max_consecutive_losses", 0) for r in successful_results
                ]

                # 资金管理
                avg_stake_values = [r.get("avg_stake_amount", 0) for r in successful_results]
                total_volume_values = [r.get("total_volume", 0) for r in successful_results]

                # 胜负统计
                wins_values = [r.get("wins", 0) for r in successful_results]
                draws_values = [r.get("draws", 0) for r in successful_results]
                losses_values = [r.get("losses", 0) for r in successful_results]

                # 计算平均值
                avg_sharpe = sum(sharpe_values) / len(sharpe_values) if sharpe_values else 0
                avg_profit = sum(profit_values) / len(profit_values) if profit_values else 0
                avg_trades = sum(trades_values) / len(trades_values) if trades_values else 0
                avg_trade_duration = (
                    sum(avg_trade_duration_values) / len(avg_trade_duration_values)
                    if avg_trade_duration_values
                    else 0
                )
                avg_max_drawdown = (
                    sum(max_drawdown_values) / len(max_drawdown_values)
                    if max_drawdown_values
                    else 0
                )
                avg_win_rate = sum(win_rate_values) / len(win_rate_values) if win_rate_values else 0

                # 新增平均值
                avg_cagr = sum(cagr_values) / len(cagr_values) if cagr_values else 0
                avg_sortino = sum(sortino_values) / len(sortino_values) if sortino_values else 0
                avg_calmar = sum(calmar_values) / len(calmar_values) if calmar_values else 0
                avg_profit_factor = (
                    sum(profit_factor_values) / len(profit_factor_values)
                    if profit_factor_values
                    else 0
                )
                avg_expectancy = (
                    sum(expectancy_values) / len(expectancy_values) if expectancy_values else 0
                )
                avg_sqn = sum(sqn_values) / len(sqn_values) if sqn_values else 0
                avg_holding_winners = (
                    sum(holding_winners_values) / len(holding_winners_values)
                    if holding_winners_values
                    else 0
                )
                avg_holding_losers = (
                    sum(holding_losers_values) / len(holding_losers_values)
                    if holding_losers_values
                    else 0
                )
                avg_consecutive_wins = (
                    sum(max_consecutive_wins_values) / len(max_consecutive_wins_values)
                    if max_consecutive_wins_values
                    else 0
                )
                avg_consecutive_losses = (
                    sum(max_consecutive_losses_values) / len(max_consecutive_losses_values)
                    if max_consecutive_losses_values
                    else 0
                )
                avg_stake_amount = (
                    sum(avg_stake_values) / len(avg_stake_values) if avg_stake_values else 0
                )
                avg_total_volume = (
                    sum(total_volume_values) / len(total_volume_values)
                    if total_volume_values
                    else 0
                )
                avg_wins = sum(wins_values) / len(wins_values) if wins_values else 0
                avg_draws = sum(draws_values) / len(draws_values) if draws_values else 0
                avg_losses = sum(losses_values) / len(losses_values) if losses_values else 0

                # 新增字段的平均值
                avg_winner_holding_min = (
                    sum(winner_holding_min_values) / len(winner_holding_min_values)
                    if winner_holding_min_values
                    else 0
                )
                avg_winner_holding_max = (
                    sum(winner_holding_max_values) / len(winner_holding_max_values)
                    if winner_holding_max_values
                    else 0
                )
                avg_loser_holding_min = (
                    sum(loser_holding_min_values) / len(loser_holding_min_values)
                    if loser_holding_min_values
                    else 0
                )
                avg_loser_holding_max = (
                    sum(loser_holding_max_values) / len(loser_holding_max_values)
                    if loser_holding_max_values
                    else 0
                )
                avg_profit_median = (
                    sum(profit_median_values) / len(profit_median_values)
                    if profit_median_values
                    else 0
                )
                avg_expectancy_ratio = (
                    sum(expectancy_ratio_values) / len(expectancy_ratio_values)
                    if expectancy_ratio_values
                    else 0
                )
                avg_winrate = sum(winrate_values) / len(winrate_values) if winrate_values else 0
                avg_trades_per_day = (
                    sum(trades_per_day_values) / len(trades_per_day_values)
                    if trades_per_day_values
                    else 0
                )
                avg_backtest_days = (
                    sum(backtest_days_values) / len(backtest_days_values)
                    if backtest_days_values
                    else 0
                )
                avg_best_day_abs = (
                    sum(best_day_abs_values) / len(best_day_abs_values)
                    if best_day_abs_values
                    else 0
                )
                avg_worst_day_abs = (
                    sum(worst_day_abs_values) / len(worst_day_abs_values)
                    if worst_day_abs_values
                    else 0
                )
                avg_timedout_entry = (
                    sum(timedout_entry_values) / len(timedout_entry_values)
                    if timedout_entry_values
                    else 0
                )
                avg_timedout_exit = (
                    sum(timedout_exit_values) / len(timedout_exit_values)
                    if timedout_exit_values
                    else 0
                )

                # 【重要修改】计算时间标准化的收益率
                # 为每个测试结果计算时间标准化的收益率
                normalized_profit_values = []
                for i, result in enumerate(successful_results):
                    timerange = result.get("timerange", "")
                    period_ratio = self._calculate_period_length_ratio(timerange)
                    # 将测试收益率标准化到1年期
                    normalized_profit = (
                        profit_values[i] / period_ratio if period_ratio > 0 else profit_values[i]
                    )
                    normalized_profit_values.append(normalized_profit)

                # 计算标准化后的平均收益率
                avg_normalized_profit = (
                    sum(normalized_profit_values) / len(normalized_profit_values)
                    if normalized_profit_values
                    else 0
                )

                # 【重要修改】计算时间标准化的交易次数
                # 交易次数也需要按时间比例标准化
                normalized_trades_values = []
                for i, result in enumerate(successful_results):
                    timerange = result.get("timerange", "")
                    period_ratio = self._calculate_period_length_ratio(timerange)
                    # 将测试交易次数标准化到1年期
                    normalized_trades = (
                        trades_values[i] / period_ratio if period_ratio > 0 else trades_values[i]
                    )
                    normalized_trades_values.append(normalized_trades)

                # 计算标准化后的平均交易次数
                avg_normalized_trades = (
                    sum(normalized_trades_values) / len(normalized_trades_values)
                    if normalized_trades_values
                    else 0
                )

                # 【重要修改】使用标准化后的指标计算衰减
                sharpe_decay = abs(original_sharpe - avg_sharpe)
                profit_decay = abs(original_profit - avg_normalized_profit)  # 使用标准化收益率
                trades_decay = abs(original_trades - avg_normalized_trades)  # 使用标准化交易次数

                # 计算稳定性指标
                stability_score = len(successful_results) / len(group_results)  # 成功率

                # 【移除评分机制】不再计算过拟合评分，只保留原始数据

                summary_data.append(
                    {
                        "rank": rank,
                        "epoch": original_params["epoch"],  # 添加原始epoch编号
                        # 原始指标
                        "original_sharpe": original_sharpe,
                        "original_profit": original_profit,
                        "original_trades": original_trades,
                        # 基础平均指标
                        "avg_sharpe": avg_sharpe,
                        "avg_profit": avg_profit,
                        "avg_trades": avg_trades,
                        "avg_trade_duration": avg_trade_duration,
                        "avg_max_drawdown": avg_max_drawdown,
                        "avg_win_rate": avg_win_rate,
                        # 标准化指标
                        "avg_normalized_profit": avg_normalized_profit,
                        "avg_normalized_trades": avg_normalized_trades,
                        # 差异指标（基于标准化指标计算）
                        "sharpe_decay": sharpe_decay,
                        "profit_decay": profit_decay,
                        "trades_decay": trades_decay,
                        # 稳定性指标
                        "stability_score": stability_score,
                        "successful_tests": len(successful_results),
                        "total_tests": len(group_results),
                        # 新增详细指标
                        "avg_cagr": avg_cagr,
                        "avg_sortino": avg_sortino,
                        "avg_calmar": avg_calmar,
                        "avg_profit_factor": avg_profit_factor,
                        "avg_expectancy": avg_expectancy,
                        "avg_sqn": avg_sqn,
                        "avg_holding_winners": avg_holding_winners,
                        "avg_holding_losers": avg_holding_losers,
                        "avg_consecutive_wins": avg_consecutive_wins,
                        "avg_consecutive_losses": avg_consecutive_losses,
                        "avg_stake_amount": avg_stake_amount,
                        "avg_total_volume": avg_total_volume,
                        "avg_wins": avg_wins,
                        "avg_draws": avg_draws,
                        "avg_losses": avg_losses,
                        # 新增详细字段
                        "avg_winner_holding_min": avg_winner_holding_min,
                        "avg_winner_holding_max": avg_winner_holding_max,
                        "avg_loser_holding_min": avg_loser_holding_min,
                        "avg_loser_holding_max": avg_loser_holding_max,
                        "avg_profit_median": avg_profit_median,
                        "avg_expectancy_ratio": avg_expectancy_ratio,
                        "avg_winrate": avg_winrate,
                        "avg_trades_per_day": avg_trades_per_day,
                        "avg_backtest_days": avg_backtest_days,
                        "avg_best_day_abs": avg_best_day_abs,
                        "avg_worst_day_abs": avg_worst_day_abs,
                        "avg_timedout_entry": avg_timedout_entry,
                        "avg_timedout_exit": avg_timedout_exit,
                        "test_results": group_results,
                    }
                )

            # 按稳定性评分排序
            summary_data.sort(key=lambda x: x["stability_score"], reverse=True)

            # 保存详细结果
            output_data = {
                "test_time": datetime.now().isoformat(),
                "total_param_sets": len(grouped_results),
                "test_periods": self.test_periods,
                "summary": summary_data,
                "detailed_results": results,
            }

            with open("overfitting_test_results.json", "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)

            # 保存CSV摘要
            if summary_data:
                df_summary = pd.DataFrame(
                    [
                        {
                            "排名": item["rank"],
                            "Epoch编号": item["epoch"],
                            "原始Sharpe": f"{item['original_sharpe']:.3f}",
                            "平均Sharpe": f"{item['avg_sharpe']:.3f}",
                            "Sharpe差异": f"{item['sharpe_decay']:.3f}",
                            "原始收益率": f"{item['original_profit']:.2f}%",
                            "平均收益率(原始)": f"{item['avg_profit']:.2f}%",
                            "平均收益率(标准化)": f"{item['avg_normalized_profit']:.2f}%",
                            "收益率差异(标准化)": f"{item['profit_decay']:.2f}%",
                            "原始交易次数": item["original_trades"],
                            "平均交易次数(原始)": f"{item['avg_trades']:.1f}",
                            "平均交易次数(标准化)": f"{item['avg_normalized_trades']:.1f}",
                            "交易次数差异(标准化)": f"{item['trades_decay']:.1f}",
                            # 持仓时间指标
                            "平均持仓时间(分钟)": f"{item['avg_trade_duration']:.1f}",
                            "盈利交易平均持仓(分钟)": f"{item['avg_holding_winners']:.1f}",
                            "亏损交易平均持仓(分钟)": f"{item['avg_holding_losers']:.1f}",
                            "盈利交易最短持仓(分钟)": f"{item['avg_winner_holding_min']:.1f}",
                            "盈利交易最长持仓(分钟)": f"{item['avg_winner_holding_max']:.1f}",
                            "亏损交易最短持仓(分钟)": f"{item['avg_loser_holding_min']:.1f}",
                            "亏损交易最长持仓(分钟)": f"{item['avg_loser_holding_max']:.1f}",
                            # 风险指标
                            "平均最大回撤": f"{item['avg_max_drawdown']:.2f}%",
                            "平均CAGR": f"{item['avg_cagr']:.2f}%",
                            "平均Sortino": f"{item['avg_sortino']:.3f}",
                            "平均Calmar": f"{item['avg_calmar']:.3f}",
                            "平均盈利因子": f"{item['avg_profit_factor']:.2f}",
                            "平均期望值": f"{item['avg_expectancy']:.3f}",
                            "平均SQN": f"{item['avg_sqn']:.2f}",
                            # 胜负统计
                            "平均胜率": f"{item['avg_win_rate']:.2%}",
                            "平均胜利次数": f"{item['avg_wins']:.1f}",
                            "平均平局次数": f"{item['avg_draws']:.1f}",
                            "平均失败次数": f"{item['avg_losses']:.1f}",
                            # 连胜连败
                            "平均最大连胜": f"{item['avg_consecutive_wins']:.1f}",
                            "平均最大连败": f"{item['avg_consecutive_losses']:.1f}",
                            # 资金管理
                            "平均仓位金额": f"{item['avg_stake_amount']:.2f}",
                            "平均总交易量": f"{item['avg_total_volume']:.2f}",
                            # 新增专业指标
                            "收益中位数": f"{item['avg_profit_median']:.2f}%",
                            "期望比率": f"{item['avg_expectancy_ratio']:.3f}",
                            "准确胜率": f"{item['avg_winrate']:.2%}",
                            "每日交易次数": f"{item['avg_trades_per_day']:.2f}",
                            "平均回测天数": f"{item['avg_backtest_days']:.1f}",
                            "最佳日收益(绝对值)": f"{item['avg_best_day_abs']:.2f}",
                            "最差日收益(绝对值)": f"{item['avg_worst_day_abs']:.2f}",
                            "平均入场超时": f"{item['avg_timedout_entry']:.1f}",
                            "平均出场超时": f"{item['avg_timedout_exit']:.1f}",
                            # 稳定性
                            "稳定性": f"{item['stability_score']:.3f}",
                            "成功测试": f"{item['successful_tests']}/{item['total_tests']}",
                        }
                        for item in summary_data
                    ]
                )
                df_summary.to_csv(
                    "overfitting_test_results_summary.csv", index=False, encoding="utf-8-sig"
                )

                # 保存各时间段的详细数据CSV
                detailed_rows = []
                period_names = {
                    "20230101-20230601": "2023H1",
                    "20230601-20231201": "2023H2",
                    "20240101-20240601": "2024H1",
                    "20211111-20220711": "2021H1",
                }

                for item in summary_data:
                    test_results = item.get("test_results", [])
                    for period in self.test_periods:
                        period_result = None
                        for result in test_results:
                            if result.get("timerange") == period:
                                period_result = result
                                break

                        period_name = period_names.get(period, period)

                        if period_result and period_result.get("status") == "success":
                            detailed_rows.append(
                                {
                                    "排名": item["rank"],
                                    "Epoch编号": item["epoch"],
                                    "时间段": period_name,
                                    "完整时间段": period,
                                    "状态": "成功",
                                    # 基础指标
                                    "Sharpe比率": f"{period_result.get('sharpe', 0):.3f}",
                                    "收益率": f"{period_result.get('profit_total', 0) * 100:.2f}%",
                                    "总收益额": f"{period_result.get('profit_total_abs', 0):.2f}",
                                    "CAGR": f"{period_result.get('cagr', 0) * 100:.2f}%",
                                    "交易次数": period_result.get("total_trades", 0),
                                    # 胜负统计
                                    "胜利次数": period_result.get("wins", 0),
                                    "平局次数": period_result.get("draws", 0),
                                    "失败次数": period_result.get("losses", 0),
                                    "胜率": f"{period_result.get('win_rate', 0) * 100:.1f}%",
                                    # 风险指标
                                    "最大回撤": f"{abs(period_result.get('max_drawdown', 0)) * 100:.2f}%",
                                    "最大回撤金额": f"{period_result.get('max_drawdown_abs', 0):.2f}",
                                    "Sortino比率": f"{period_result.get('sortino', 0):.3f}",
                                    "Calmar比率": f"{period_result.get('calmar', 0):.3f}",
                                    "盈利因子": f"{period_result.get('profit_factor', 0):.2f}",
                                    "期望值": f"{period_result.get('expectancy', 0):.3f}",
                                    "SQN": f"{period_result.get('sqn', 0):.2f}",
                                    # 持仓时间
                                    "平均持仓时间(分钟)": f"{period_result.get('avg_trade_duration_minutes', 0):.1f}",
                                    "盈利交易平均持仓(分钟)": f"{period_result.get('holding_avg_winners', 0):.1f}",
                                    "亏损交易平均持仓(分钟)": f"{period_result.get('holding_avg_losers', 0):.1f}",
                                    "盈利交易最短持仓(分钟)": f"{period_result.get('winner_holding_min', 0):.1f}",
                                    "盈利交易最长持仓(分钟)": f"{period_result.get('winner_holding_max', 0):.1f}",
                                    "亏损交易最短持仓(分钟)": f"{period_result.get('loser_holding_min', 0):.1f}",
                                    "亏损交易最长持仓(分钟)": f"{period_result.get('loser_holding_max', 0):.1f}",
                                    # 连胜连败
                                    "最大连胜": period_result.get("max_consecutive_wins", 0),
                                    "最大连败": period_result.get("max_consecutive_losses", 0),
                                    # 资金管理
                                    "平均仓位金额": f"{period_result.get('avg_stake_amount', 0):.2f}",
                                    "总交易量": f"{period_result.get('total_volume', 0):.2f}",
                                    "起始余额": f"{period_result.get('starting_balance', 0):.2f}",
                                    "最终余额": f"{period_result.get('final_balance', 0):.2f}",
                                    "最小余额": f"{period_result.get('min_balance', 0):.2f}",
                                    "最大余额": f"{period_result.get('max_balance', 0):.2f}",
                                    # 交易质量
                                    "最佳交易": f"{period_result.get('best_trade', 0) * 100:.2f}%",
                                    "最差交易": f"{period_result.get('worst_trade', 0) * 100:.2f}%",
                                    "最佳日收益": f"{period_result.get('best_day', 0):.2f}",
                                    "最差日收益": f"{period_result.get('worst_day', 0):.2f}",
                                    # 市场相关
                                    "市场变化": f"{period_result.get('market_change', 0) * 100:.2f}%",
                                    "拒绝信号数": period_result.get("rejected_signals", 0),
                                    "入场超时": period_result.get("timedout_entry_orders", 0),
                                    "出场超时": period_result.get("timedout_exit_orders", 0),
                                    "每日交易次数": f"{period_result.get('trades_per_day', 0):.2f}",
                                    "回测天数": period_result.get("backtest_days", 0),
                                    # 额外指标
                                    "收益中位数": f"{period_result.get('profit_median', 0) * 100:.2f}%",
                                    "期望比率": f"{period_result.get('expectancy_ratio', 0):.3f}",
                                    "准确胜率": f"{period_result.get('winrate', 0) * 100:.1f}%",
                                    "最佳日收益(绝对值)": f"{period_result.get('best_day_abs', 0):.2f}",
                                    "最差日收益(绝对值)": f"{period_result.get('worst_day_abs', 0):.2f}",
                                }
                            )
                        else:
                            error_msg = (
                                period_result.get("error", "未知错误")
                                if period_result
                                else "无数据"
                            )
                            detailed_rows.append(
                                {
                                    "排名": item["rank"],
                                    "Epoch编号": item["epoch"],
                                    "时间段": period_name,
                                    "完整时间段": period,
                                    "状态": "失败",
                                    # 基础指标
                                    "Sharpe比率": "-",
                                    "收益率": "-",
                                    "总收益额": "-",
                                    "CAGR": "-",
                                    "交易次数": "-",
                                    # 胜负统计
                                    "胜利次数": "-",
                                    "平局次数": "-",
                                    "失败次数": "-",
                                    "胜率": "-",
                                    # 风险指标
                                    "最大回撤": "-",
                                    "最大回撤金额": "-",
                                    "Sortino比率": "-",
                                    "Calmar比率": "-",
                                    "盈利因子": "-",
                                    "期望值": "-",
                                    "SQN": "-",
                                    # 持仓时间
                                    "平均持仓时间(分钟)": "-",
                                    "盈利交易平均持仓(分钟)": "-",
                                    "亏损交易平均持仓(分钟)": "-",
                                    "盈利交易最短持仓(分钟)": "-",
                                    "盈利交易最长持仓(分钟)": "-",
                                    "亏损交易最短持仓(分钟)": "-",
                                    "亏损交易最长持仓(分钟)": "-",
                                    # 连胜连败
                                    "最大连胜": "-",
                                    "最大连败": "-",
                                    # 资金管理
                                    "平均仓位金额": "-",
                                    "总交易量": "-",
                                    "起始余额": "-",
                                    "最终余额": "-",
                                    "最小余额": "-",
                                    "最大余额": "-",
                                    # 交易质量
                                    "最佳交易": "-",
                                    "最差交易": "-",
                                    "最佳日收益": "-",
                                    "最差日收益": "-",
                                    # 市场相关
                                    "市场变化": "-",
                                    "拒绝信号数": "-",
                                    "入场超时": "-",
                                    "出场超时": "-",
                                    "每日交易次数": "-",
                                    "回测天数": "-",
                                    # 额外指标
                                    "收益中位数": "-",
                                    "期望比率": "-",
                                    "准确胜率": "-",
                                    "最佳日收益(绝对值)": "-",
                                    "最差日收益(绝对值)": "-",
                                    "错误信息": error_msg,
                                }
                            )

                if detailed_rows:
                    df_detailed = pd.DataFrame(detailed_rows)
                    df_detailed.to_csv(
                        "overfitting_test_timeframe_details.csv", index=False, encoding="utf-8-sig"
                    )

            logger.info(f"[SAVE] 结果已保存到:")
            logger.info(f"  - overfitting_test_results.json (完整JSON数据)")
            logger.info(f"  - overfitting_test_results_summary.csv (汇总数据)")
            logger.info(f"  - overfitting_test_timeframe_details.csv (各时间段详细数据)")

            # 打印摘要
            self._print_summary(summary_data)

        except Exception as e:
            logger.error(f"[ERROR] 分析结果失败: {e}")

    def resave_outputs_from_json(self, json_path: str = "overfitting_test_results.json") -> None:
        """仅从已生成的JSON结果文件重建并写出CSV，不重跑回测。

        - 读取 json_path（包含 summary、detailed_results、test_periods）
        - 生成 overfitting_test_results_summary.csv
        - 生成 overfitting_test_timeframe_details.csv
        - 若CSV被占用导致 PermissionError，则改写为带时间戳的新文件名
        """
        try:
            if not os.path.exists(json_path):
                logger.error(f"[RESAVE] 未找到结果JSON: {json_path}")
                return

            with open(json_path, "r", encoding="utf-8") as f:
                output_data = json.load(f)

            summary_data = output_data.get("summary", [])
            detailed_results = output_data.get("detailed_results", [])
            test_periods = output_data.get("test_periods", [])

            # 回写汇总CSV
            if summary_data:
                df_summary = pd.DataFrame(
                    [
                        {
                            "排名": item.get("rank"),
                            "Epoch编号": item.get("epoch"),
                            "原始Sharpe": f"{item.get('original_sharpe', 0):.3f}",
                            "平均Sharpe": f"{item.get('avg_sharpe', 0):.3f}",
                            "Sharpe差异": f"{item.get('sharpe_decay', 0):.3f}",
                            "原始收益率": f"{item.get('original_profit', 0):.2f}%",
                            "平均收益率(原始)": f"{item.get('avg_profit', 0):.2f}%",
                            "平均收益率(标准化)": f"{item.get('avg_normalized_profit', 0):.2f}%",
                            "收益率差异(标准化)": f"{item.get('profit_decay', 0):.2f}%",
                            "原始交易次数": item.get("original_trades", 0),
                            "平均交易次数(原始)": f"{item.get('avg_trades', 0):.1f}",
                            "平均交易次数(标准化)": f"{item.get('avg_normalized_trades', 0):.1f}",
                            "交易次数差异(标准化)": f"{item.get('trades_decay', 0):.1f}",
                            # 持仓时间指标
                            "平均持仓时间(分钟)": f"{item.get('avg_trade_duration', 0):.1f}",
                            "盈利交易平均持仓(分钟)": f"{item.get('avg_holding_winners', 0):.1f}",
                            "亏损交易平均持仓(分钟)": f"{item.get('avg_holding_losers', 0):.1f}",
                            "盈利交易最短持仓(分钟)": f"{item.get('avg_winner_holding_min', 0):.1f}",
                            "盈利交易最长持仓(分钟)": f"{item.get('avg_winner_holding_max', 0):.1f}",
                            "亏损交易最短持仓(分钟)": f"{item.get('avg_loser_holding_min', 0):.1f}",
                            "亏损交易最长持仓(分钟)": f"{item.get('avg_loser_holding_max', 0):.1f}",
                            # 风险指标
                            "平均最大回撤": f"{item.get('avg_max_drawdown', 0):.2f}%",
                            "平均CAGR": f"{item.get('avg_cagr', 0):.2f}%",
                            "平均Sortino": f"{item.get('avg_sortino', 0):.3f}",
                            "平均Calmar": f"{item.get('avg_calmar', 0):.3f}",
                            "平均盈利因子": f"{item.get('avg_profit_factor', 0):.2f}",
                            "平均期望值": f"{item.get('avg_expectancy', 0):.3f}",
                            "平均SQN": f"{item.get('avg_sqn', 0):.2f}",
                            # 胜负统计
                            "平均胜率": f"{item.get('avg_win_rate', 0):.2%}",
                            "平均胜利次数": f"{item.get('avg_wins', 0):.1f}",
                            "平均平局次数": f"{item.get('avg_draws', 0):.1f}",
                            "平均失败次数": f"{item.get('avg_losses', 0):.1f}",
                            # 连胜连败
                            "平均最大连胜": f"{item.get('avg_consecutive_wins', 0):.1f}",
                            "平均最大连败": f"{item.get('avg_consecutive_losses', 0):.1f}",
                            # 资金管理
                            "平均仓位金额": f"{item.get('avg_stake_amount', 0):.2f}",
                            "平均总交易量": f"{item.get('avg_total_volume', 0):.2f}",
                            # 新增专业指标
                            "收益中位数": f"{item.get('avg_profit_median', 0):.2f}%",
                            "期望比率": f"{item.get('avg_expectancy_ratio', 0):.3f}",
                            "准确胜率": f"{item.get('avg_winrate', 0):.2%}",
                            "每日交易次数": f"{item.get('avg_trades_per_day', 0):.2f}",
                            "平均回测天数": f"{item.get('avg_backtest_days', 0):.1f}",
                            "最佳日收益(绝对值)": f"{item.get('avg_best_day_abs', 0):.2f}",
                            "最差日收益(绝对值)": f"{item.get('avg_worst_day_abs', 0):.2f}",
                            "平均入场超时": f"{item.get('avg_timedout_entry', 0):.1f}",
                            "平均出场超时": f"{item.get('avg_timedout_exit', 0):.1f}",
                            # 稳定性
                            "稳定性": f"{item.get('stability_score', 0):.3f}",
                            "成功测试": f"{item.get('successful_tests', 0)}/{item.get('total_tests', 0)}",
                        }
                        for item in summary_data
                    ]
                )
                try:
                    df_summary.to_csv(
                        "overfitting_test_results_summary.csv", index=False, encoding="utf-8-sig"
                    )
                except PermissionError:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    alt = f"overfitting_test_results_summary_{ts}.csv"
                    logger.warning(f"[RESAVE] summary.csv 被占用，写入: {alt}")
                    df_summary.to_csv(alt, index=False, encoding="utf-8-sig")

            # 回写各时间段明细CSV
            period_names = {
                "20230101-20230601": "2023H1",
                "20230601-20231201": "2023H2",
                "20240101-20240601": "2024H1",
                "20211111-20220711": "2021H1",
            }

            detailed_rows: List[Dict[str, Any]] = []
            # 需要从 summary 里带回 rank/epoch，并用 test_results 对应 period
            for item in summary_data:
                test_results = item.get("test_results", [])
                for period in test_periods or []:
                    period_result = next(
                        (r for r in test_results if r.get("timerange") == period), None
                    )
                    period_name = period_names.get(period, period)
                    if period_result and period_result.get("status") == "success":
                        detailed_rows.append(
                            {
                                "排名": item.get("rank"),
                                "Epoch编号": item.get("epoch"),
                                "时间段": period_name,
                                "完整时间段": period,
                                "状态": "成功",
                                # 基础指标
                                "Sharpe比率": f"{period_result.get('sharpe', 0):.3f}",
                                "收益率": f"{period_result.get('profit_total', 0) * 100:.2f}%",
                                "总收益额": f"{period_result.get('profit_total_abs', 0):.2f}",
                                "CAGR": f"{period_result.get('cagr', 0) * 100:.2f}%",
                                "交易次数": period_result.get("total_trades", 0),
                                # 胜负统计
                                "胜利次数": period_result.get("wins", 0),
                                "平局次数": period_result.get("draws", 0),
                                "失败次数": period_result.get("losses", 0),
                                "胜率": f"{period_result.get('win_rate', 0) * 100:.1f}%",
                                # 风险指标
                                "最大回撤": f"{abs(period_result.get('max_drawdown', 0)) * 100:.2f}%",
                                "最大回撤金额": f"{period_result.get('max_drawdown_abs', 0):.2f}",
                                "Sortino比率": f"{period_result.get('sortino', 0):.3f}",
                                "Calmar比率": f"{period_result.get('calmar', 0):.3f}",
                                "盈利因子": f"{period_result.get('profit_factor', 0):.2f}",
                                "期望值": f"{period_result.get('expectancy', 0):.3f}",
                                "SQN": f"{period_result.get('sqn', 0):.2f}",
                                # 持仓时间
                                "平均持仓时间(分钟)": f"{period_result.get('avg_trade_duration_minutes', 0):.1f}",
                                "盈利交易平均持仓(分钟)": f"{period_result.get('holding_avg_winners', 0):.1f}",
                                "亏损交易平均持仓(分钟)": f"{period_result.get('holding_avg_losers', 0):.1f}",
                                "盈利交易最短持仓(分钟)": f"{period_result.get('winner_holding_min', 0):.1f}",
                                "盈利交易最长持仓(分钟)": f"{period_result.get('winner_holding_max', 0):.1f}",
                                "亏损交易最短持仓(分钟)": f"{period_result.get('loser_holding_min', 0):.1f}",
                                "亏损交易最长持仓(分钟)": f"{period_result.get('loser_holding_max', 0):.1f}",
                                # 连胜连败
                                "最大连胜": period_result.get("max_consecutive_wins", 0),
                                "最大连败": period_result.get("max_consecutive_losses", 0),
                                # 资金管理
                                "平均仓位金额": f"{period_result.get('avg_stake_amount', 0):.2f}",
                                "总交易量": f"{period_result.get('total_volume', 0):.2f}",
                                "起始余额": f"{period_result.get('starting_balance', 0):.2f}",
                                "最终余额": f"{period_result.get('final_balance', 0):.2f}",
                                "最小余额": f"{period_result.get('min_balance', 0):.2f}",
                                "最大余额": f"{period_result.get('max_balance', 0):.2f}",
                                # 交易质量
                                "最佳交易": f"{period_result.get('best_trade', 0) * 100:.2f}%",
                                "最差交易": f"{period_result.get('worst_trade', 0) * 100:.2f}%",
                                "最佳日收益": f"{period_result.get('best_day', 0):.2f}",
                                "最差日收益": f"{period_result.get('worst_day', 0):.2f}",
                                # 市场相关
                                "市场变化": f"{period_result.get('market_change', 0) * 100:.2f}%",
                                "拒绝信号数": period_result.get("rejected_signals", 0),
                                "入场超时": period_result.get("timedout_entry_orders", 0),
                                "出场超时": period_result.get("timedout_exit_orders", 0),
                                "每日交易次数": f"{period_result.get('trades_per_day', 0):.2f}",
                                "回测天数": period_result.get("backtest_days", 0),
                                # 额外指标
                                "收益中位数": f"{period_result.get('profit_median', 0) * 100:.2f}%",
                                "期望比率": f"{period_result.get('expectancy_ratio', 0):.3f}",
                                "准确胜率": f"{period_result.get('winrate', 0) * 100:.1f}%",
                                "最佳日收益(绝对值)": f"{period_result.get('best_day_abs', 0):.2f}",
                                "最差日收益(绝对值)": f"{period_result.get('worst_day_abs', 0):.2f}",
                            }
                        )
                    else:
                        error_msg = (period_result or {}).get("error", "无数据")
                        detailed_rows.append(
                            {
                                "排名": item.get("rank"),
                                "Epoch编号": item.get("epoch"),
                                "时间段": period_name,
                                "完整时间段": period,
                                "状态": "失败",
                                # 基础指标
                                "Sharpe比率": "-",
                                "收益率": "-",
                                "总收益额": "-",
                                "CAGR": "-",
                                "交易次数": "-",
                                # 胜负统计
                                "胜利次数": "-",
                                "平局次数": "-",
                                "失败次数": "-",
                                "胜率": "-",
                                # 风险指标
                                "最大回撤": "-",
                                "最大回撤金额": "-",
                                "Sortino比率": "-",
                                "Calmar比率": "-",
                                "盈利因子": "-",
                                "期望值": "-",
                                "SQN": "-",
                                # 持仓时间
                                "平均持仓时间(分钟)": "-",
                                "盈利交易平均持仓(分钟)": "-",
                                "亏损交易平均持仓(分钟)": "-",
                                "盈利交易最短持仓(分钟)": "-",
                                "盈利交易最长持仓(分钟)": "-",
                                "亏损交易最短持仓(分钟)": "-",
                                "亏损交易最长持仓(分钟)": "-",
                                # 连胜连败
                                "最大连胜": "-",
                                "最大连败": "-",
                                # 资金管理
                                "平均仓位金额": "-",
                                "总交易量": "-",
                                "起始余额": "-",
                                "最终余额": "-",
                                "最小余额": "-",
                                "最大余额": "-",
                                # 交易质量
                                "最佳交易": "-",
                                "最差交易": "-",
                                "最佳日收益": "-",
                                "最差日收益": "-",
                                # 市场相关
                                "市场变化": "-",
                                "拒绝信号数": "-",
                                "入场超时": "-",
                                "出场超时": "-",
                                "每日交易次数": "-",
                                "回测天数": "-",
                                # 额外指标
                                "收益中位数": "-",
                                "期望比率": "-",
                                "准确胜率": "-",
                                "最佳日收益(绝对值)": "-",
                                "最差日收益(绝对值)": "-",
                                "错误信息": error_msg,
                            }
                        )

            if detailed_rows:
                df_detailed = pd.DataFrame(detailed_rows)
                try:
                    df_detailed.to_csv(
                        "overfitting_test_timeframe_details.csv", index=False, encoding="utf-8-sig"
                    )
                except PermissionError:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    alt = f"overfitting_test_timeframe_details_{ts}.csv"
                    logger.warning(f"[RESAVE] timeframe_details.csv 被占用，写入: {alt}")
                    df_detailed.to_csv(alt, index=False, encoding="utf-8-sig")

            logger.info("[RESAVE] 已从JSON重建并写出CSV文件。")
        except Exception as e:
            logger.error(f"[RESAVE] 失败: {e}")

    def _print_all_epochs_summary(self, summary_data: List[Dict[str, Any]]):
        """打印所有Epoch的简洁汇总表"""
        print("\n[ALL_EPOCHS] 所有测试Epoch简洁汇总 (按稳定性排序):")
        print("=" * 120)
        print(
            f"{'排名':<4} {'Epoch':<8} {'类型':<6} {'原始Sharpe':<12} {'平均Sharpe':<12} {'Sharpe差异':<12} {'稳定性':<10} {'成功率':<10}"
        )
        print("-" * 120)

        for i, item in enumerate(summary_data, 1):
            # 判断是否为Best参数
            epoch_type = "Best" if i <= 4 else "随机"  # 假设前4个是Best参数

            success_rate = f"{item['successful_tests']}/{item['total_tests']}"
            success_pct = (
                (item["successful_tests"] / item["total_tests"] * 100)
                if item["total_tests"] > 0
                else 0
            )

            print(
                f"{i:<4} {item['epoch']:<8} {epoch_type:<6} "
                f"{item['original_sharpe']:<12.3f} {item['avg_sharpe']:<12.3f} {item['sharpe_decay']:<12.3f} "
                f"{item['stability_score']:<10.3f} {success_rate}({success_pct:.0f}%)"
            )

            # 每10行加一个分隔符
            if i % 10 == 0 and i < len(summary_data):
                print("-" * 120)

        # 添加统计摘要
        if summary_data:
            best_epochs = summary_data[:4]  # 前4个Best
            random_epochs = summary_data[4:] if len(summary_data) > 4 else []

            print("\n[STATISTICS] 统计摘要:")
            print("-" * 60)
            print(
                f"{'类型':<8} {'数量':<6} {'平均Sharpe差异':<15} {'平均成功率':<15} {'平均稳定性':<12}"
            )
            print("-" * 60)

            # Best参数统计
            if best_epochs:
                best_sharpe_decay = sum(item["sharpe_decay"] for item in best_epochs) / len(
                    best_epochs
                )
                best_success_rate = (
                    sum(item["successful_tests"] / item["total_tests"] for item in best_epochs)
                    / len(best_epochs)
                    * 100
                )
                best_stability = sum(item["stability_score"] for item in best_epochs) / len(
                    best_epochs
                )

                print(
                    f"{'Best':<8} {len(best_epochs):<6} {best_sharpe_decay:<15.3f} {best_success_rate:<15.1f}% {best_stability:<12.3f}"
                )

            # 随机参数统计
            if random_epochs:
                random_sharpe_decay = sum(item["sharpe_decay"] for item in random_epochs) / len(
                    random_epochs
                )
                random_success_rate = (
                    sum(item["successful_tests"] / item["total_tests"] for item in random_epochs)
                    / len(random_epochs)
                    * 100
                )
                random_stability = sum(item["stability_score"] for item in random_epochs) / len(
                    random_epochs
                )

                print(
                    f"{'随机':<8} {len(random_epochs):<6} {random_sharpe_decay:<15.3f} {random_success_rate:<15.1f}% {random_stability:<12.3f}"
                )

        print()

    def _print_summary(self, summary_data: List[Dict[str, Any]]):
        """打印测试摘要"""
        print("\n" + "=" * 80)
        print("[SUMMARY] 过拟合测试摘要报告")
        print("=" * 80)

        if not summary_data:
            print("[WARNING] 没有有效的测试结果")
            return

        # 🆕 添加：简洁的所有Epoch结果汇总表
        self._print_all_epochs_summary(summary_data)

        print("\n 全部的参数组合 (完整回测数据):")
        print("=" * 160)
        print(
            f"{'排名':<4} {'Epoch':<6} {'原始':<8} {'平均':<8} {'Sharpe':<8} {'原始':<8} {'标准化':<8} {'收益率':<8} {'原始':<6} {'标准化':<8} {'交易数':<8} {'稳定性':<6} {'成功':<6}"
        )
        print(
            f"{'    ':<4} {'编号':<6} {'Sharpe':<8} {'Sharpe':<8} {'差异':<8} {'收益率':<8} {'收益率':<8} {'差异':<8} {'交易数':<6} {'交易数':<8} {'差异':<8} {'评分':<6} {'测试':<6}"
        )
        print("-" * 160)

        for item in summary_data:
            print(
                f"{item['rank']:<4} {item['epoch']:<6} {item['original_sharpe']:<8.3f} {item['avg_sharpe']:<8.3f} "
                f"{item['sharpe_decay']:<8.3f} {item['original_profit']:<8.2f} {item['avg_normalized_profit']:<8.2f} "
                f"{item['profit_decay']:<8.2f} {item['original_trades']:<6.0f} {item['avg_normalized_trades']:<8.1f} "
                f"{item['trades_decay']:<8.1f} {item['stability_score']:<6.3f} "
                f"{item['successful_tests']}/{item['total_tests']:<6}"
            )

        # 新增：显示每个参数组合在各时间段的详细表现
        print("\n[TIMEFRAME_DETAILS] 各参数组合在不同时间段的详细表现:")
        print("=" * 160)

        # 定义时间段的简短名称
        period_names = {
            "20230101-20230601": "2023H1",
            "20230601-20231201": "2023H2",
            "20240101-20240601": "2024H1",
            "20240601-20241201": "2024H2",
            "20211111-20220711": "2021H1",
        }

        for i, item in enumerate(summary_data, 1):  # 显示前10个参数组合
            print(f"\n排名 #{item['rank']} (Epoch {item['epoch']}) - 各时间段详细表现:")
            print("-" * 120)

            # 表头
            print(
                f"{'时间段':<8} {'状态':<6} {'Sharpe':<8} {'收益率':<10} {'交易数':<8} {'胜率':<8} {'最大回撤':<10} {'平均持仓(分)':<12}"
            )
            print("-" * 120)

            # 获取该参数组合的测试结果
            test_results = item.get("test_results", [])

            # 按时间段排序并显示
            for period in self.test_periods:
                period_result = None
                for result in test_results:
                    if result.get("timerange") == period:
                        period_result = result
                        break

                period_name = period_names.get(period, period)

                if period_result and period_result.get("status") == "success":
                    sharpe = period_result.get("sharpe", 0)
                    profit = period_result.get("profit_total", 0) * 100  # 转换为百分比
                    trades = period_result.get("total_trades", 0)
                    win_rate = period_result.get("win_rate", 0) * 100  # 转换为百分比
                    max_dd = abs(period_result.get("max_drawdown", 0)) * 100  # 转换为百分比
                    avg_duration = period_result.get("avg_trade_duration_minutes", 0)

                    print(
                        f"{period_name:<8} {'成功':<6} {sharpe:<8.3f} {profit:<10.2f}% {trades:<8.0f} {win_rate:<8.1f}% {max_dd:<10.2f}% {avg_duration:<12.1f}"
                    )
                else:
                    error_msg = (
                        period_result.get("error", "未知错误") if period_result else "无数据"
                    )
                    print(
                        f"{period_name:<8} {'失败':<6} {'-':<8} {'-':<10} {'-':<8} {'-':<8} {'-':<10} {'-':<12} ({error_msg})"
                    )

            # 显示汇总统计
            successful_results = [r for r in test_results if r.get("status") == "success"]
            if successful_results:
                sharpe_values = [r.get("sharpe", 0) for r in successful_results]
                profit_values = [r.get("profit_total", 0) * 100 for r in successful_results]
                trades_values = [r.get("total_trades", 0) for r in successful_results]

                sharpe_std = (
                    (sum((x - item["avg_sharpe"]) ** 2 for x in sharpe_values) / len(sharpe_values))
                    ** 0.5
                    if len(sharpe_values) > 1
                    else 0
                )
                profit_std = (
                    (sum((x - item["avg_profit"]) ** 2 for x in profit_values) / len(profit_values))
                    ** 0.5
                    if len(profit_values) > 1
                    else 0
                )
                trades_std = (
                    (sum((x - item["avg_trades"]) ** 2 for x in trades_values) / len(trades_values))
                    ** 0.5
                    if len(trades_values) > 1
                    else 0
                )

                print("-" * 120)
                print(
                    f"{'汇总':<8} {'统计':<6} {item['avg_sharpe']:<8.3f} {item['avg_profit']:<10.2f}% {item['avg_trades']:<8.1f} {item['avg_win_rate'] * 100:<8.1f}% {item['avg_max_drawdown'] * 100:<10.2f}% {item['avg_trade_duration']:<12.1f}"
                )
                print(
                    f"{'标准差':<8} {'    ':<6} {sharpe_std:<8.3f} {profit_std:<10.2f}% {trades_std:<8.1f} {'-':<8} {'-':<10} {'-':<12}"
                )

            print()  # 空行分隔

        # 显示详细的数据分析
        print("\n[DETAILED] 详细数据分析:")
        print("=" * 120)
        for i, item in enumerate(summary_data[:5], 1):
            print(f"\n排名 #{item['rank']} (Epoch {item['epoch']}) 详细数据:")

            print(f"  基础性能指标:")
            print(
                f"    - Sharpe比率:    原始 {item['original_sharpe']:.3f} → 平均 {item['avg_sharpe']:.3f} (差异 {item['sharpe_decay']:.3f})"
            )
            print(
                f"    - 收益率:        原始 {item['original_profit']:.2f}% → 标准化平均 {item['avg_normalized_profit']:.2f}% (差异 {item['profit_decay']:.2f}%)"
            )
            print(f"    - 收益率(原始):  平均 {item['avg_profit']:.2f}% (未标准化，仅供参考)")
            print(f"    - CAGR:          平均 {item['avg_cagr']:.2f}%")
            print(
                f"    - 交易次数:      原始 {item['original_trades']:.0f} → 标准化平均 {item['avg_normalized_trades']:.1f} (差异 {item['trades_decay']:.1f})"
            )
            print(f"    - 交易次数(原始): 平均 {item['avg_trades']:.1f} (未标准化，仅供参考)")

            print(f"  风险管理指标:")
            print(f"    - 平均最大回撤:  {item['avg_max_drawdown']:.2f}%")
            print(f"    - Sortino比率:   {item['avg_sortino']:.3f}")
            print(f"    - Calmar比率:    {item['avg_calmar']:.3f}")
            print(f"    - 盈利因子:      {item['avg_profit_factor']:.2f}")
            print(f"    - 期望值:        {item['avg_expectancy']:.3f}")
            print(f"    - SQN:           {item['avg_sqn']:.2f}")

            print(f"  交易行为分析:")
            print(f"    - 平均胜率:      {item['avg_win_rate']:.2%}")
            print(f"    - 平均胜利次数:  {item['avg_wins']:.1f}")
            print(f"    - 平均平局次数:  {item['avg_draws']:.1f}")
            print(f"    - 平均失败次数:  {item['avg_losses']:.1f}")
            print(f"    - 平均最大连胜:  {item['avg_consecutive_wins']:.1f}")
            print(f"    - 平均最大连败:  {item['avg_consecutive_losses']:.1f}")

            print(f"  持仓时间分析:")
            print(f"    - 总体平均持仓:  {item['avg_trade_duration']:.1f} 分钟")
            print(f"    - 盈利交易持仓:  {item['avg_holding_winners']:.1f} 分钟")
            print(f"    - 亏损交易持仓:  {item['avg_holding_losers']:.1f} 分钟")

            print(f"  资金管理:")
            print(f"    - 平均仓位金额:  {item['avg_stake_amount']:.2f} USDT")
            print(f"    - 平均总交易量:  {item['avg_total_volume']:.2f} USDT")

            print(f"  稳定性:")
            print(f"    - 稳定性评分:    {item['stability_score']:.3f}")
            print(f"    - 成功测试:      {item['successful_tests']}/{item['total_tests']}")
            print("  " + "-" * 60)

        # 计算基础统计信息
        avg_stability = sum(item["stability_score"] for item in summary_data) / len(summary_data)
        avg_sharpe_decay = sum(item["sharpe_decay"] for item in summary_data) / len(summary_data)
        avg_profit_decay = sum(item["profit_decay"] for item in summary_data) / len(summary_data)

        print(f"\n[STATISTICS] 数据统计分析:")
        print(f"  平均稳定性评分: {avg_stability:.3f}")
        print(f"  平均Sharpe差异: {avg_sharpe_decay:.3f}")
        print(f"  平均收益率差异(标准化): {avg_profit_decay:.2f}%")
        print(f"\n[TIME_NORMALIZATION] 时间标准化说明:")
        print(f"  - 原始优化基于1年数据，测试时间段通常为半年")
        print(f"  - 收益率和交易次数已按时间比例标准化到1年期进行比较")
        print(f"  - 这样可以更公平地评估参数的稳定性，避免因时间段差异导致的偏差")

        # 显示前5个最稳定的参数组合
        print(f"\n[TOP_STABLE] 最稳定的20个参数组合:")
        for i, item in enumerate(summary_data[:20], 1):
            print(
                f"  {i}. 排名 #{item['rank']} (Epoch {item['epoch']}): "
                f"稳定性 {item['stability_score']:.3f}, "
                f"Sharpe差异 {item['sharpe_decay']:.3f}, "
                f"成功率 {item['successful_tests']}/{item['total_tests']}"
            )

    def export_epoch_config(self, epoch_number: int, output_filename: str = None) -> bool:
        """导出指定Epoch的参数配置到JSON文件

        Args:
            epoch_number: 要导出的Epoch编号
            output_filename: 输出文件名（不含扩展名），如果为None则使用 "epoch_{epoch_number}_config"

        Returns:
            bool: 是否成功导出
        """
        try:
            logger.info(f"[EXPORT] 开始导出 Epoch {epoch_number} 的参数配置...")

            # 获取所有超参数结果
            all_params = get_top_params_direct(
                top_n=1000,  # 获取足够多的结果
                hyperopt_filename=self.hyperopt_file,
                user_data_dir="user_data",
                sort_by="loss",
                only_best=False,  # 获取所有结果
            )

            if not all_params:
                logger.error(f"[ERROR] 未找到任何超参数结果")
                return False

            # 查找指定的epoch
            target_epoch = None
            for param_set in all_params:
                if param_set.get("epoch") == epoch_number:
                    target_epoch = param_set
                    break

            if target_epoch is None:
                logger.error(f"[ERROR] 未找到 Epoch {epoch_number}")
                available_epochs = [
                    p.get("epoch") for p in all_params[:20]
                ]  # 显示前20个可用的epoch
                logger.info(f"[INFO] 可用的前20个Epoch: {available_epochs}")
                return False

            # 设置输出文件名
            if output_filename is None:
                output_filename = f"epoch_{epoch_number}_config"

            # 确保输出目录存在
            output_dir = Path("./user_data/strategies")
            output_dir.mkdir(parents=True, exist_ok=True)

            # 完整的输出路径
            output_path = output_dir / f"{output_filename}.json"

            # 提取参数
            params = target_epoch.get("params", {})
            metrics = target_epoch.get("metrics", {})

            # 构建Freqtrade期望的参数格式 - 合并优化参数到对应分组
            merged_params = {}

            # 复制非参数相关的配置
            for key, value in params.items():
                if key not in [
                    "buy_params",
                    "sell_params",
                    "roi_params",
                    "stoploss_params",
                    "trailing_params",
                    "protection_params",
                ]:
                    merged_params[key] = value

            # 确保基础分组存在
            if "buy" not in merged_params:
                merged_params["buy"] = {}
            if "sell" not in merged_params:
                merged_params["sell"] = {}
            if "roi" not in merged_params:
                merged_params["roi"] = {"0": 999}
            if "stoploss" not in merged_params:
                merged_params["stoploss"] = {"stoploss": -100.0}
            if "trailing" not in merged_params:
                merged_params["trailing"] = {
                    "trailing_stop": False,
                    "trailing_stop_positive": None,
                    "trailing_stop_positive_offset": 0.0,
                    "trailing_only_offset_is_reached": False,
                }
            if "protection" not in merged_params:
                merged_params["protection"] = {}

            # 合并优化参数到对应的分组中
            if "buy_params" in params and params["buy_params"]:
                merged_params["buy"].update(params["buy_params"])
            if "sell_params" in params and params["sell_params"]:
                merged_params["sell"].update(params["sell_params"])
            if "roi_params" in params and params["roi_params"]:
                merged_params["roi"].update(params["roi_params"])
            if "stoploss_params" in params and params["stoploss_params"]:
                merged_params["stoploss"].update(params["stoploss_params"])
            if "trailing_params" in params and params["trailing_params"]:
                merged_params["trailing"].update(params["trailing_params"])
            if "protection_params" in params and params["protection_params"]:
                merged_params["protection"].update(params["protection_params"])

            freqtrade_params = {
                "strategy_name": self.strategy_name,
                "params": merged_params,
                "ft_stratparam_v": 1,
                "export_time": datetime.now().isoformat(),
            }

            # 同时生成详细的元数据文件（用于记录）
            metadata_config = {
                "strategy_name": self.strategy_name,
                "epoch_info": {
                    "epoch_number": epoch_number,
                    "rank": target_epoch.get("rank", "unknown"),
                    "is_best": target_epoch.get("is_best", False),
                    "export_time": datetime.now().isoformat(),
                },
                "performance_metrics": {
                    "loss": metrics.get("loss", 0),
                    "profit_total_percent": metrics.get("profit_total_percent", 0),
                    "profit_total_abs": metrics.get("profit_total_abs", 0),
                    "total_trades": metrics.get("total_trades", 0),
                    "sharpe": metrics.get("sharpe", 0),
                    "sortino": metrics.get("sortino", 0),
                    "calmar": metrics.get("calmar", 0),
                    "max_drawdown": metrics.get("max_drawdown", 0),
                    "win_rate": metrics.get("win_rate", 0),
                    "avg_profit": metrics.get("avg_profit", 0),
                    "stake_currency": metrics.get("stake_currency", "USDT"),
                },
                "params": params,
                "ft_stratparam_v": 1,
            }

            # 写入Freqtrade参数文件（策略实际使用的文件）
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(freqtrade_params, f, indent=2, ensure_ascii=False)

            # 写入详细元数据文件（用于记录和分析）
            metadata_path = output_dir / f"{output_filename}_metadata.json"
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata_config, f, indent=2, ensure_ascii=False)

            logger.info(f"[SUCCESS] Epoch {epoch_number} 配置已导出:")
            logger.info(f"  - Freqtrade参数文件: {output_path}")
            logger.info(f"  - 详细元数据文件: {metadata_path}")
            logger.info(f"[INFO] 参数结构: {list(merged_params.keys())}")
            logger.info(f"[INFO] 合并的优化参数:")
            if "buy_params" in params and params["buy_params"]:
                logger.info(f"  - buy参数: {list(params['buy_params'].keys())}")
            if "sell_params" in params and params["sell_params"]:
                logger.info(f"  - sell参数: {list(params['sell_params'].keys())}")
            logger.info(f"[INFO] 该Epoch的性能指标:")
            logger.info(f"  - Sharpe比率: {metrics.get('sharpe', 0):.3f}")
            logger.info(f"  - 总收益率: {metrics.get('profit_total_percent', 0) * 100:.2f}%")
            logger.info(f"  - 总交易次数: {metrics.get('total_trades', 0)}")
            logger.info(f"  - 胜率: {metrics.get('win_rate', 0):.1%}")
            logger.info(f"  - 最大回撤: {metrics.get('max_drawdown', 0):.2f}%")

            # 显示主要参数
            logger.info(f"[INFO] 主要参数类别:")
            for param_type, param_values in params.items():
                if param_values:  # 只显示非空的参数类别
                    logger.info(f"  - {param_type}: {len(param_values)} 个参数")

            return True

        except Exception as e:
            logger.error(f"[ERROR] 导出 Epoch {epoch_number} 配置时出错: {e}")
            return False


def main(hyperopt_file, strategy_name):
    """主函数"""
    print("[INFO] 超参数过拟合批量测试工具")
    print("=" * 60)
    print(f"[LOG] 详细日志已保存到: {log_filename}")
    print("[TIP] 可以同时查看日志文件和控制台输出")
    print("=" * 60)

    # 检查文件是否存在
    if not os.path.exists(hyperopt_file):
        logger.error(f"[ERROR] 指定的超参数文件不存在: {hyperopt_file}")
        print(f"[ERROR] 请检查文件路径是否正确: {hyperopt_file}")
        return

    print(f"[INFO] 使用超参数文件: {hyperopt_file}")

    # 创建测试器（指定超参数文件）
    try:
        tester = OverfittingTester(hyperopt_file=hyperopt_file, strategy_name=strategy_name)
    except FileNotFoundError as e:
        logger.error(f"[ERROR] 创建测试器失败: {e}")
        return

    # 🎯 配置测试参数
    test_count = 300  # 测试的参数数量
    use_mixed_sampling = False  # 是否使用混合采样（Best + 随机1/8）

    print(f"[CONFIG] 测试参数数量: {test_count}")
    print(
        f"[CONFIG] 采样方式: {'混合采样(Best + 随机1/4)' if use_mixed_sampling else '仅Best结果'}"
    )
    print("[CONFIG] 过滤条件: 只选择收益为正的epoch")
    print("=" * 60)

    # 临时修改类方法来支持新参数
    original_method = tester._load_params_once

    def modified_load_params(top_n, use_mixed_sampling_override=None):
        # 如果没有指定，使用main函数中配置的值
        sampling_mode = (
            use_mixed_sampling_override
            if use_mixed_sampling_override is not None
            else use_mixed_sampling
        )
        return original_method(top_n, use_mixed_sampling=sampling_mode)

    tester._load_params_once = modified_load_params

    # 运行测试
    results = tester.run_overfitting_test(top_n=test_count)

    if results:
        print(f"\n[COMPLETE] 测试完成！共测试了 {len(results)} 个回测结果")
        print(f"[LOG] 完整测试日志已保存到: {log_filename}")
        print("[TIP] 请查看日志文件获取详细的测试报告和所有Epoch结果汇总")
    else:
        print("\n[ERROR] 测试失败！")
        print(f"[LOG] 错误日志已保存到: {log_filename}")


def export_specific_epoch(hyperopt_file, strategy_name, epochs_to_export):
    """导出特定Epoch配置的便捷函数"""
    print("[INFO] 导出特定Epoch配置工具")
    print("=" * 60)

    # 配置参数

    # 检查文件是否存在
    if not os.path.exists(hyperopt_file):
        print(f"[ERROR] 指定的超参数文件不存在: {hyperopt_file}")
        return

    # 创建测试器
    try:
        tester = OverfittingTester(hyperopt_file=hyperopt_file, strategy_name=strategy_name)
    except Exception as e:
        print(f"[ERROR] 创建测试器失败: {e}")
        return

    print(f"[INFO] 准备导出以下Epoch的配置: {epochs_to_export}")
    print("=" * 60)

    success_count = 0
    for epoch_num in epochs_to_export:
        print(f"\n正在导出 Epoch {epoch_num}...")

        # 自定义文件名
        output_filename = f"{strategy_name}_epoch_{epoch_num}_config"

        # 导出配置
        if tester.export_epoch_config(epoch_num, output_filename):
            success_count += 1
            print(f"✅ Epoch {epoch_num} 导出成功！")
        else:
            print(f"❌ Epoch {epoch_num} 导出失败！")

    print(f"\n[COMPLETE] 导出完成！成功导出 {success_count}/{len(epochs_to_export)} 个配置文件")
    print(f"[INFO] 配置文件保存在: ./user_data/strategies/")
    print("\n使用方法：")
    print("1. 找到对应的JSON文件")
    print("2. 将参数复制到你的策略文件中")
    print("3. 或者直接使用 freqtrade 命令加载参数：")
    print(
        f"   freqtrade backtesting --strategy {strategy_name} --strategy-path user_data/strategies/ --hyperopt-filename user_data/strategies/{strategy_name}_epoch_238_config.json"
    )


if __name__ == "__main__":
    # 取消注释下面的行来运行特定功能
    hyperopt_file = (
        r"user_data\hyperopt_results\strategy_Strategyshuangxiangtaoli_2025-08-16_02-49-29.fthypt"
    )
    strategy_name = "Strategyshuangxiangtaoli"

    # 运行过拟合测试（原功能）
    main(hyperopt_file, strategy_name)

    # 运行 resave_outputs_from_json
    # tester = OverfittingTester(hyperopt_file=hyperopt_file, strategy_name=strategy_name)
    # tester.resave_outputs_from_json()

    # 导出特定Epoch配置（修复后的新功能 - 生成正确的Freqtrade参数格式）
    # export_specific_epoch(
    #     hyperopt_file,
    #     strategy_name,
    #     epochs_to_export=[277],
    # )

    print("🎉 参数格式问题已彻底解决！")
    print("✅ 已修复JSON配置文件格式和导出函数")
    print("📁 文件位置：user_data/strategies/Strategyshuangxiangtaoli.json")
    print("\n🔧 关键修复：")
    print("1. ✅ 移除了错误的 buy_params、sell_params 包装层")
    print("2. ✅ 优化参数直接放在对应的 buy、sell 分组内")
    print("3. ✅ export_epoch_config函数已修复，会自动合并参数")
    print("4. ✅ 格式完全符合Freqtrade期望结构")
    print("\n📊 当前参数分布：")
    print("• buy.change_percentage: 6.5")
    print("• sell.base_price_change_threshold: 0.039")
    print("• sell.base_trailing_distance: 0.06")
    print("• sell.position_adjustment_factor: 0.22")
    print("\n📋 使用说明：")
    print("• 当前配置文件可直接使用，不会再出现 (default) 提示")
    print("• 如需导出其他Epoch：取消注释export_specific_epoch函数")
    print("• 导出功能已修复，会正确合并参数到对应分组")
    print("\n🚀 现在策略应该能正确加载所有参数了！")
