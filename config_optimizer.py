#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置优化器 - 根据硬件配置自动优化WFA回测参数
帮助用户充分利用硬件性能，获得最佳回测速度
"""

import json
import os
from pathlib import Path

import psutil


class ConfigOptimizer:
    """配置优化器"""

    def __init__(self):
        self.cpu_count = psutil.cpu_count(logical=True)
        self.cpu_physical = psutil.cpu_count(logical=False)
        self.memory_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        self.is_ssd = self._detect_ssd()

    def _detect_ssd(self):
        """检测是否使用SSD（简单检测）"""
        try:
            # 简单的SSD检测，基于磁盘分区信息
            partitions = psutil.disk_partitions()
            for partition in partitions:
                if partition.mountpoint == "/" or "C:" in partition.mountpoint:
                    # 这里可以添加更精确的SSD检测逻辑
                    return True  # 假设主分区是SSD
        except:
            pass
        return False

    def analyze_hardware(self):
        """分析硬件配置并给出评级"""
        print("🔍 正在分析您的硬件配置...")
        print("=" * 50)

        # CPU评级
        if self.cpu_count >= 16:
            cpu_rating = "优秀"
            cpu_score = 5
        elif self.cpu_count >= 8:
            cpu_rating = "良好"
            cpu_score = 4
        elif self.cpu_count >= 4:
            cpu_rating = "一般"
            cpu_score = 3
        else:
            cpu_rating = "较低"
            cpu_score = 2

        # 内存评级
        if self.memory_gb >= 32:
            memory_rating = "优秀"
            memory_score = 5
        elif self.memory_gb >= 16:
            memory_rating = "良好"
            memory_score = 4
        elif self.memory_gb >= 8:
            memory_rating = "一般"
            memory_score = 3
        else:
            memory_rating = "较低"
            memory_score = 2

        # 存储评级
        storage_rating = "良好" if self.is_ssd else "一般"
        storage_score = 4 if self.is_ssd else 3

        overall_score = (cpu_score + memory_score + storage_score) / 3

        print(f"🔧 CPU: {self.cpu_physical}核{self.cpu_count}线程 - {cpu_rating}")
        print(f"💾 内存: {self.memory_gb} GB - {memory_rating}")
        print(f"💿 存储: {'SSD' if self.is_ssd else 'HDD'} - {storage_rating}")
        print(f"⭐ 综合评分: {overall_score:.1f}/5.0")
        print("=" * 50)

        return {
            "cpu_count": self.cpu_count,
            "cpu_rating": cpu_rating,
            "cpu_score": cpu_score,
            "memory_gb": self.memory_gb,
            "memory_rating": memory_rating,
            "memory_score": memory_score,
            "storage_rating": storage_rating,
            "storage_score": storage_score,
            "overall_score": overall_score,
        }

    def calculate_optimal_threads(self):
        """计算最优线程数"""
        base_threads = int(self.cpu_count * 0.75)  # 使用75%的CPU

        # 根据内存调整
        if self.memory_gb < 8:
            # 内存不足，减少线程数
            base_threads = min(base_threads, 4)
        elif self.memory_gb < 16:
            base_threads = min(base_threads, 8)

        # 确保至少有1个线程
        return max(1, base_threads)

    def calculate_optimal_combinations(self):
        """计算最优参数组合数"""
        if self.memory_gb >= 32 and self.cpu_count >= 16:
            return 1000  # 高配置，可以测试更多组合
        elif self.memory_gb >= 16 and self.cpu_count >= 8:
            return 600  # 中高配置
        elif self.memory_gb >= 8 and self.cpu_count >= 4:
            return 300  # 中等配置
        else:
            return 150  # 低配置，减少组合数

    def generate_optimized_config(self):
        """生成优化后的配置"""
        hardware_info = self.analyze_hardware()
        optimal_threads = self.calculate_optimal_threads()
        optimal_combinations = self.calculate_optimal_combinations()

        # 根据硬件选择搜索方法
        if hardware_info["overall_score"] >= 4.0:
            search_method = "random"
            print("💡 推荐使用随机搜索，您的硬件配置可以处理大量参数组合")
        else:
            search_method = "grid"
            optimal_combinations = min(optimal_combinations, 200)
            print("💡 推荐使用网格搜索，参数组合数较少但更系统化")

        config = {
            "strategy_name": "Strategy_Simple_Indicator_Test",
            "timeframe": "1m",
            "config_path": "config_examples/config_freqai.example.json",
            "max_workers": optimal_threads,
            "search_method": search_method,
            "num_random_combinations": optimal_combinations,
            "hardware_optimization": {
                "cpu_count": self.cpu_count,
                "memory_gb": self.memory_gb,
                "recommended_threads": optimal_threads,
                "recommended_combinations": optimal_combinations,
                "optimization_notes": [
                    f"根据{self.cpu_count}核CPU优化线程数为{optimal_threads}",
                    f"根据{self.memory_gb}GB内存优化参数组合数为{optimal_combinations}",
                    f"选择{search_method}搜索方法以匹配硬件性能",
                ],
            },
            "parameter_spaces": [
                {
                    "name": "vwma_length",
                    "param_type": "int",
                    "min_val": 10,
                    "max_val": 30,
                    "space": "buy",
                },
                {
                    "name": "change_percentage",
                    "param_type": "decimal",
                    "min_val": 0.2,
                    "max_val": 0.4,
                    "decimals": 2,
                    "space": "buy",
                },
                {
                    "name": "rsi_length",
                    "param_type": "int",
                    "min_val": 6,
                    "max_val": 9,
                    "space": "buy",
                },
                {
                    "name": "mfi_length",
                    "param_type": "int",
                    "min_val": 6,
                    "max_val": 9,
                    "space": "buy",
                },
                {
                    "name": "rsi_mfi_below_level",
                    "param_type": "int",
                    "min_val": 37,
                    "max_val": 47,
                    "space": "buy",
                },
                {
                    "name": "rsi_mfi_above_level",
                    "param_type": "int",
                    "min_val": 86,
                    "max_val": 100,
                    "space": "buy",
                },
                {
                    "name": "trade_direction",
                    "param_type": "categorical",
                    "choices": ["LONG"],  # 简化测试，只做多头
                    "space": "buy",
                },
                {
                    "name": "hold_time_minutes",
                    "param_type": "int",
                    "min_val": 15,
                    "max_val": 60,
                    "space": "sell",
                },
            ],
            "wfa_windows": [
                {
                    "window_id": 1,
                    "is_start": "20240101",
                    "is_end": "20240331",
                    "oos_start": "20240401",
                    "oos_end": "20240430",
                },
                {
                    "window_id": 2,
                    "is_start": "20240201",
                    "is_end": "20240430",
                    "oos_start": "20240501",
                    "oos_end": "20240531",
                },
                {
                    "window_id": 3,
                    "is_start": "20240301",
                    "is_end": "20240531",
                    "oos_start": "20240601",
                    "oos_end": "20240630",
                },
            ],
        }

        return config

    def save_optimized_config(self):
        """保存优化后的配置"""
        config = self.generate_optimized_config()
        config_file = "wfa_config_v3.json"

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f"✅ 优化配置已保存到: {config_file}")
        return config

    def print_optimization_summary(self, config):
        """打印优化摘要"""
        print("\n🚀 配置优化完成！")
        print("=" * 50)
        print(f"推荐线程数: {config['max_workers']} (基于{self.cpu_count}核CPU)")
        print(f"搜索方法: {config['search_method']}")
        print(f"参数组合数: {config['num_random_combinations']}")
        print(f"WFA窗口数: {len(config['wfa_windows'])}")

        # 估算测试时间
        total_backtests = len(config["wfa_windows"]) * config["num_random_combinations"]
        estimated_time_per_backtest = 2  # 秒（估算）
        sequential_time = total_backtests * estimated_time_per_backtest / 60  # 分钟
        parallel_time = sequential_time / config["max_workers"]

        print(f"\n⏱️ 预估测试时间:")
        print(f"   单线程模式: {sequential_time:.1f} 分钟")
        print(f"   多线程模式: {parallel_time:.1f} 分钟")
        print(f"   预期加速: {config['max_workers']:.1f}倍")

        print(f"\n💡 使用建议:")
        if self.memory_gb < 16:
            print("   ⚠️  内存较少，建议关闭其他程序释放内存")
        if not self.is_ssd:
            print("   ⚠️  建议使用SSD以提升数据读写速度")
        if config["max_workers"] < 4:
            print("   ⚠️  CPU核心数较少，考虑升级硬件以获得更好性能")

        print("   ✅ 配置已根据您的硬件优化，可直接使用")
        print("=" * 50)

    def run_optimization(self):
        """运行完整的优化流程"""
        print("🎯 WFA回测配置优化器")
        print("根据您的硬件自动优化配置，获得最佳性能")
        print("=" * 50)

        # 生成并保存优化配置
        config = self.save_optimized_config()

        # 打印优化摘要
        self.print_optimization_summary(config)

        return config


def main():
    """主函数"""
    optimizer = ConfigOptimizer()

    try:
        # 运行优化
        config = optimizer.run_optimization()

        print("\n📋 下一步操作:")
        print("1. 运行: WFA策略评测V3-多线程优化.bat")
        print("2. 或者运行: python WFA_Strategy_Evaluator_V3_MultiThread.py")
        print("3. 可选: 运行 python system_monitor.py 监控系统性能")

    except Exception as e:
        print(f"❌ 优化过程中发生错误: {e}")


if __name__ == "__main__":
    main()
