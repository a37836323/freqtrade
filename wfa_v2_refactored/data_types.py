#!/usr/bin/env python3
"""
WFA数据类型定义模块
包含所有WFA相关的数据结构定义
"""

from dataclasses import dataclass
from typing import Any


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
class BacktestResult:
    """回测结果"""

    params: dict[str, Any]
    performance: dict[str, Any] | None = None
    success: bool = False
    error_message: str | None = None


@dataclass
class WFAResult:
    """单个WFA窗口的结果"""

    window: WFAWindow
    is_results: list[BacktestResult]
    best_params: dict[str, Any] | None = None
    is_best_performance: dict[str, Any] | None = None
    oos_performance: dict[str, Any] | None = None
    optimization_success: bool = False
    oos_backtest_success: bool = False
    error_message: str | None = None


@dataclass
class WFAConfig:
    """WFA配置"""

    strategy_name: str = "Strategy_Simple_Indicator_Test"
    config_path: str = "./user_data/config.json"
    timeframe: str = "30m"
    is_window_months: int = 24
    oos_window_months: int = 6
    roll_step_months: int = 6
    start_date: str = "20220101"
    end_date: str = "20241201"
    optimization_method: str = "random"  # "grid" or "random"
    max_param_combinations: int = 300
