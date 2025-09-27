#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Freqtrade参数生成器模块
复用freqtrade的参数检测和组合生成功能
"""

import logging
import random
import sys
from itertools import product
from pathlib import Path
from typing import Any


# import numpy as np  # 暂时不需要


# 添加freqtrade主目录到Python路径
current_dir = Path(__file__).parent
freqtrade_dir = current_dir.parent / "freqtrade"
if freqtrade_dir.exists():
    sys.path.insert(0, str(freqtrade_dir.parent))
    print(f"[DEBUG] 添加freqtrade路径: {freqtrade_dir.parent}")
else:
    print(f"[WARNING] freqtrade目录不存在: {freqtrade_dir}")


logger = logging.getLogger(__name__)


class FreqtradeParameterGenerator:
    """基于Freqtrade参数系统的参数生成器"""

    def __init__(self, strategy_name: str, config_path: str):
        self.strategy_name = strategy_name
        self.config_path = config_path
        self.strategy_instance = None
        self.buy_dimensions = []
        self.sell_dimensions = []
        self._load_strategy()

    def _load_strategy(self):
        """加载策略实例并提取参数空间（轻量级方式）"""
        try:
            import json
            from pathlib import Path

            from freqtrade.optimize.hyperopt.hyperopt_auto import HyperOptAuto
            from freqtrade.resolvers.strategy_resolver import StrategyResolver
            from freqtrade.strategy.hyper import detect_parameters

            # 创建最小配置，避免完整初始化
            with open(self.config_path, "r", encoding="utf-8") as f:
                base_config = json.load(f)

            # 创建轻量级配置，只包含必要参数
            minimal_config = {
                "strategy": self.strategy_name,
                "user_data_dir": Path(base_config.get("user_data_dir", "./user_data")),
                "strategy_path": base_config.get("strategy_path", None),
                # 必要的默认值，避免初始化错误
                "timeframe": base_config.get("timeframe", "5m"),
                "stake_currency": base_config.get("stake_currency", "USDT"),
                "stake_amount": base_config.get("stake_amount", 1000),
                "dry_run": True,
                # 避免交易所初始化
                "exchange": {"name": "binance", "sandbox": True},
                # 超参数空间设置
                "spaces": ["buy", "sell"],
            }

            logger.info(f"[FREQTRADE_PARAM] 使用轻量级方式加载策略: {self.strategy_name}")

            # 直接使用策略解析器加载策略，避免完整的 Backtesting 初始化
            self.strategy_instance = StrategyResolver._load_strategy(
                self.strategy_name,
                config=minimal_config,
                extra_dir=minimal_config.get("strategy_path"),
            )

            # 初始化策略参数（但不需要完整的超参数设置）
            self.strategy_instance.ft_load_params_from_file()
            self.strategy_instance.ft_load_hyper_params(hyperopt=True)

            logger.info(f"[FREQTRADE_PARAM] 策略加载成功，开始提取参数空间...")

            # 直接从策略实例提取参数
            buy_params = []
            sell_params = []

            # 使用策略的参数检测功能
            for param_name, param in detect_parameters(self.strategy_instance, "buy"):
                if param.optimize:  # 只提取需要优化的参数
                    try:
                        space_obj = param.get_space(param_name)
                        space_obj.name = param_name

                        # space_obj 已经包含了所有必要属性：high, low, step 等
                        buy_params.append(space_obj)

                        # 从 space_obj 获取属性进行日志显示
                        step = getattr(space_obj, "step", None)
                        decimals = getattr(space_obj, "decimals", 0)

                        logger.info(
                            f"[FREQTRADE_PARAM] 找到Buy参数: {param_name} = {self._describe_dimension(space_obj)} (step={step})"
                        )
                    except Exception as e:
                        logger.warning(f"[FREQTRADE_PARAM] 跳过Buy参数 {param_name}: {e}")

            for param_name, param in detect_parameters(self.strategy_instance, "sell"):
                if param.optimize:  # 只提取需要优化的参数
                    try:
                        space_obj = param.get_space(param_name)
                        space_obj.name = param_name

                        # space_obj 已经包含了所有必要属性：high, low, step 等
                        sell_params.append(space_obj)

                        # 从 space_obj 获取属性进行日志显示
                        step = getattr(space_obj, "step", None)
                        decimals = getattr(space_obj, "decimals", 0)

                        logger.info(
                            f"[FREQTRADE_PARAM] 找到Sell参数: {param_name} = {self._describe_dimension(space_obj)} (step={step})"
                        )
                    except Exception as e:
                        logger.warning(f"[FREQTRADE_PARAM] 跳过Sell参数 {param_name}: {e}")

            self.buy_dimensions = buy_params
            self.sell_dimensions = sell_params

            logger.info(f"[FREQTRADE_PARAM] 成功加载策略 {self.strategy_name}")
            logger.info(f"[FREQTRADE_PARAM] Buy参数维度: {len(self.buy_dimensions)}")
            logger.info(f"[FREQTRADE_PARAM] Sell参数维度: {len(self.sell_dimensions)}")

            if not buy_params and not sell_params:
                logger.warning(
                    f"[FREQTRADE_PARAM] ⚠️  策略 {self.strategy_name} 中没有找到可优化的参数！"
                )
                logger.info(f"[FREQTRADE_PARAM] 💡 请确保策略中定义了带有 optimize=True 的参数")

        except Exception as e:
            logger.error(f"[FREQTRADE_PARAM] 加载策略失败: {e}")
            import traceback

            logger.error(f"[FREQTRADE_PARAM] 详细错误: {traceback.format_exc()}")
            raise

    def _describe_dimension(self, dim) -> str:
        """描述参数维度"""
        try:
            if hasattr(dim, "choices"):
                return f"Categorical{dim.choices}"
            elif hasattr(dim, "low") and hasattr(dim, "high"):
                step = getattr(dim, "step", None)
                if step is not None and step != 1:
                    return f"Decimal[{dim.low}, {dim.high}] step={step}"
                else:
                    return f"Integer[{dim.low}, {dim.high}]"
            else:
                return str(type(dim).__name__)
        except:
            return str(type(dim).__name__)

    def generate_grid_combinations(self, max_combinations: int = 1000) -> list[dict[str, Any]]:
        """生成网格搜索参数组合"""
        logger.info(f"[FREQTRADE_PARAM] 开始生成网格搜索参数组合（最大{max_combinations}个）...")

        if not self.buy_dimensions and not self.sell_dimensions:
            logger.warning("[FREQTRADE_PARAM] 没有找到可优化的参数")
            return [{"buy_params": {}, "sell_params": {}}]

        combinations = []

        # 生成buy参数的所有可能值
        buy_param_values = []
        for dim in self.buy_dimensions:
            values = self._generate_dimension_values(dim, grid_size=8)  # 每个参数最多8个值
            buy_param_values.append((dim.name, values))

        # 生成sell参数的所有可能值
        sell_param_values = []
        for dim in self.sell_dimensions:
            values = self._generate_dimension_values(dim, grid_size=8)
            sell_param_values.append((dim.name, values))

        # 计算总组合数
        total_combinations = 1
        for _, values in buy_param_values + sell_param_values:
            total_combinations *= len(values)

        logger.info(f"[FREQTRADE_PARAM] 理论总组合数: {total_combinations}")

        # 生成组合
        if buy_param_values:
            buy_names, buy_vals = zip(*buy_param_values)
        else:
            buy_names, buy_vals = [], []

        if sell_param_values:
            sell_names, sell_vals = zip(*sell_param_values)
        else:
            sell_names, sell_vals = [], []

        # 生成所有buy组合
        if buy_vals:
            buy_combos = list(product(*buy_vals))
        else:
            buy_combos = [()]

        # 生成所有sell组合
        if sell_vals:
            sell_combos = list(product(*sell_vals))
        else:
            sell_combos = [()]

        # 组合buy和sell参数
        for buy_combo in buy_combos:
            if len(combinations) >= max_combinations:
                break

            buy_dict = dict(zip(buy_names, buy_combo)) if buy_names else {}

            for sell_combo in sell_combos:
                if len(combinations) >= max_combinations:
                    break

                sell_dict = dict(zip(sell_names, sell_combo)) if sell_names else {}

                combination = {"buy_params": buy_dict, "sell_params": sell_dict}
                combinations.append(combination)

        logger.info(f"[FREQTRADE_PARAM] 实际生成组合数: {len(combinations)}")

        # 打印前几个组合作为验证
        if combinations:
            logger.info("[FREQTRADE_PARAM] 🔍 网格搜索参数组合示例：")
            for i, combo in enumerate(combinations[:3]):  # 显示前3个组合
                logger.info(f"[FREQTRADE_PARAM]   组合 {i + 1}: {combo}")

        return combinations

    def generate_random_combinations(self, num_combinations: int = 300) -> list[dict[str, Any]]:
        """生成随机搜索参数组合"""
        logger.info(f"[FREQTRADE_PARAM] 开始生成随机搜索参数组合（{num_combinations}个）...")

        if not self.buy_dimensions and not self.sell_dimensions:
            logger.warning("[FREQTRADE_PARAM] 没有找到可优化的参数")
            return [{"buy_params": {}, "sell_params": {}}]

        combinations = []
        random.seed(42)  # 确保可重现

        for i in range(num_combinations):
            buy_dict = {}
            sell_dict = {}

            # 随机生成buy参数
            for dim in self.buy_dimensions:
                buy_dict[dim.name] = self._generate_random_value(dim)

            # 随机生成sell参数
            for dim in self.sell_dimensions:
                sell_dict[dim.name] = self._generate_random_value(dim)

            combination = {"buy_params": buy_dict, "sell_params": sell_dict}
            combinations.append(combination)

        logger.info(f"[FREQTRADE_PARAM] 生成完成: {len(combinations)} 个随机组合")

        # 打印前几个组合作为验证
        if combinations:
            logger.info("[FREQTRADE_PARAM] 🎲 随机搜索参数组合示例：")
            for i, combo in enumerate(combinations[:3]):  # 显示前3个组合
                logger.info(f"[FREQTRADE_PARAM]   组合 {i + 1}: {combo}")

        return combinations

    def _generate_dimension_values(self, dim, grid_size: int = 8) -> list[Any]:
        """为单个维度生成网格值"""
        try:
            # 分类参数
            if hasattr(dim, "choices"):
                return dim.choices

            # 数值参数
            elif hasattr(dim, "low") and hasattr(dim, "high"):
                low, high = dim.low, dim.high
                step_size = getattr(dim, "step", None)
                decimals = getattr(dim, "decimals", 0)

                if step_size is not None and step_size != 1:
                    # 有步长的参数（通常是小数参数）
                    # 计算在给定步长下的所有可能值
                    num_steps = int((high - low) / step_size) + 1

                    if num_steps <= grid_size:
                        # 如果总步数不超过网格大小，返回所有可能值
                        values = []
                        current = low
                        while current <= high:
                            if decimals > 0:
                                values.append(round(current, decimals))
                            else:
                                values.append(current)
                            current += step_size
                        # 确保包含上界
                        if values and abs(values[-1] - high) > step_size / 2:
                            if decimals > 0:
                                values.append(round(high, decimals))
                            else:
                                values.append(high)
                    else:
                        # 均匀选择网格点
                        grid_step = max(1, num_steps // (grid_size - 1))
                        values = []
                        for i in range(0, num_steps, grid_step):
                            value = low + i * step_size
                            if value <= high:
                                if decimals > 0:
                                    values.append(round(value, decimals))
                                else:
                                    values.append(value)
                        # 确保包含上界
                        if len(values) == 0 or abs(values[-1] - high) > step_size / 2:
                            if decimals > 0:
                                values.append(round(high, decimals))
                            else:
                                values.append(high)

                    return values

                else:
                    # 整数参数
                    low, high = int(low), int(high)
                    if high - low + 1 <= grid_size:
                        return list(range(low, high + 1))
                    else:
                        step = max(1, (high - low) // (grid_size - 1))
                        values = list(range(low, high + 1, step))
                        if values[-1] != high:
                            values.append(high)
                        return values

            else:
                logger.warning(f"[FREQTRADE_PARAM] 未知参数类型: {type(dim)}")
                return [0]

        except Exception as e:
            logger.error(f"[FREQTRADE_PARAM] 生成维度值失败: {e}")
            return [0]

    def _generate_random_value(self, dim) -> Any:
        """为单个维度生成随机值"""
        try:
            # 分类参数
            if hasattr(dim, "choices"):
                return random.choice(dim.choices)

            # 数值参数
            elif hasattr(dim, "low") and hasattr(dim, "high"):
                low, high = dim.low, dim.high
                step_size = getattr(dim, "step", None)
                decimals = getattr(dim, "decimals", 0)

                if step_size is not None and step_size != 1:
                    # 有步长的参数，按步长随机选择
                    num_steps = int((high - low) / step_size)
                    random_step = random.randint(0, num_steps)
                    value = low + random_step * step_size

                    # 确保不超过上界
                    if value > high:
                        value = high

                    # 根据精度四舍五入
                    if decimals > 0:
                        value = round(value, decimals)

                    return value
                else:
                    # 整数参数
                    return random.randint(int(low), int(high))

            else:
                logger.warning(f"[FREQTRADE_PARAM] 未知参数类型: {type(dim)}")
                return 0

        except Exception as e:
            logger.error(f"[FREQTRADE_PARAM] 生成随机值失败: {e}")
            return 0
