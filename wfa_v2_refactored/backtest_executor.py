#!/usr/bin/env python3
"""
回测执行模块
负责单次回测的执行和结果处理
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# 添加freqtrade主目录到Python路径
current_dir = Path(__file__).parent
freqtrade_dir = current_dir.parent / "freqtrade"
if freqtrade_dir.exists():
    sys.path.insert(0, str(freqtrade_dir.parent))
    print(f"[DEBUG] 添加freqtrade路径: {freqtrade_dir.parent}")
else:
    print(f"[WARNING] freqtrade目录不存在: {freqtrade_dir}")


try:
    from .data_types import BacktestResult
except ImportError:
    from data_types import BacktestResult


logger = logging.getLogger(__name__)


class BacktestExecutor:
    """回测执行器"""

    def __init__(self, strategy_name: str, config_path: str, timeframe: str = "30m"):
        self.strategy_name = strategy_name
        self.config_path = config_path
        self.timeframe = timeframe

    def run_backtest(self, timerange: str, params: dict[str, Any]) -> BacktestResult:
        """运行单次回测"""
        try:
            # 更新策略参数
            if not self._update_strategy_params(params):
                return BacktestResult(
                    params=params, success=False, error_message="更新策略参数失败"
                )

            # 导入必要模块
            from freqtrade.commands.optimize_commands import setup_optimize_configuration
            from freqtrade.enums import RunMode
            from freqtrade.optimize.backtesting import Backtesting

            # 构建回测参数
            args = {
                "config": [self.config_path],
                "strategy": self.strategy_name,
                "timeframe": self.timeframe,
                "timerange": timerange,
                "verbosity": 0,
                "logfile": None,
                "export": "none",
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
                return BacktestResult(params=params, success=False, error_message="回测结果为None")

            if "strategy" not in backtesting.results:
                return BacktestResult(
                    params=params, success=False, error_message="回测结果中没有strategy键"
                )

            strategy_results = backtesting.results["strategy"]
            if self.strategy_name not in strategy_results:
                return BacktestResult(
                    params=params, success=False, error_message=f"未找到策略 {self.strategy_name}"
                )

            result = strategy_results[self.strategy_name]

            if isinstance(result, dict):
                performance = self._extract_performance_metrics(result)
                return BacktestResult(params=params, success=True, performance=performance)
            else:
                return BacktestResult(
                    params=params, success=False, error_message="回测结果格式错误"
                )

        except Exception as e:
            return BacktestResult(params=params, success=False, error_message=str(e))

        finally:
            # 清理资源
            if "backtesting" in locals():
                try:
                    backtesting.cleanup()
                except:
                    pass

    def _update_strategy_params(self, params: dict[str, Any]) -> bool:
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

            # 更新buy参数
            if "buy_params" in params and params["buy_params"]:
                if "buy" not in strategy_config["params"]:
                    strategy_config["params"]["buy"] = {}
                strategy_config["params"]["buy"].update(params["buy_params"])

            # 更新sell参数
            if "sell_params" in params and params["sell_params"]:
                if "sell" not in strategy_config["params"]:
                    strategy_config["params"]["sell"] = {}
                strategy_config["params"]["sell"].update(params["sell_params"])

            # 更新时间戳
            strategy_config["export_time"] = datetime.now().isoformat()

            # 写入文件
            with open(strategy_json_path, "w", encoding="utf-8") as f:
                json.dump(strategy_config, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            logger.error(f"[BACKTEST] 更新策略参数失败: {e}")
            return False

    def _extract_performance_metrics(self, result: dict[str, Any]) -> dict[str, Any]:
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
