#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统性能监控器 - 实时监控WFA回测期间的系统资源使用情况
帮助用户了解硬件性能瓶颈，优化配置
"""

import json
import os
import threading
import time
from datetime import datetime

import psutil


class SystemMonitor:
    """系统性能监控器"""

    def __init__(self, log_interval=5, save_to_file=True):
        self.log_interval = log_interval
        self.save_to_file = save_to_file
        self.monitoring = False
        self.monitor_thread = None
        self.performance_data = []

    def get_system_info(self):
        """获取系统基本信息"""
        info = {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "count_logical": psutil.cpu_count(logical=True),
                "count_physical": psutil.cpu_count(logical=False),
                "usage_percent": psutil.cpu_percent(interval=1, percpu=False),
                "usage_per_core": psutil.cpu_percent(interval=1, percpu=True),
                "freq_current": psutil.cpu_freq().current if psutil.cpu_freq() else "N/A",
                "freq_max": psutil.cpu_freq().max if psutil.cpu_freq() else "N/A",
            },
            "memory": {
                "total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                "used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
                "usage_percent": psutil.virtual_memory().percent,
            },
            "disk": {
                "total_gb": round(psutil.disk_usage(".").total / (1024**3), 2),
                "free_gb": round(psutil.disk_usage(".").free / (1024**3), 2),
                "used_gb": round(psutil.disk_usage(".").used / (1024**3), 2),
                "usage_percent": round(
                    (psutil.disk_usage(".").used / psutil.disk_usage(".").total) * 100, 2
                ),
            },
        }

        # 添加网络信息（如果有的话）
        try:
            net_io = psutil.net_io_counters()
            info["network"] = {
                "bytes_sent_mb": round(net_io.bytes_sent / (1024**2), 2),
                "bytes_recv_mb": round(net_io.bytes_recv / (1024**2), 2),
            }
        except:
            info["network"] = {"status": "unavailable"}

        return info

    def print_system_status(self, info):
        """打印系统状态到控制台"""
        print("\n" + "=" * 60)
        print(f"🖥️  系统监控 - {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 60)

        # CPU信息
        print(f"🔧 CPU:")
        print(
            f"   核心数: {info['cpu']['count_physical']} 物理 / {info['cpu']['count_logical']} 逻辑"
        )
        print(f"   使用率: {info['cpu']['usage_percent']:.1f}%")
        if info["cpu"]["freq_current"] != "N/A":
            print(
                f"   频率: {info['cpu']['freq_current']:.0f} MHz / {info['cpu']['freq_max']:.0f} MHz"
            )

        # 内存信息
        print(f"💾 内存:")
        print(f"   总计: {info['memory']['total_gb']} GB")
        print(f"   已用: {info['memory']['used_gb']} GB ({info['memory']['usage_percent']:.1f}%)")
        print(f"   可用: {info['memory']['available_gb']} GB")

        # 磁盘信息
        print(f"💿 磁盘:")
        print(f"   总计: {info['disk']['total_gb']} GB")
        print(f"   已用: {info['disk']['used_gb']} GB ({info['disk']['usage_percent']:.1f}%)")
        print(f"   可用: {info['disk']['free_gb']} GB")

        # 性能建议
        self.print_performance_tips(info)

    def print_performance_tips(self, info):
        """根据当前状态给出性能建议"""
        print(f"💡 性能建议:")

        # CPU建议
        cpu_usage = info["cpu"]["usage_percent"]
        if cpu_usage > 90:
            print(f"   ⚠️  CPU使用率过高 ({cpu_usage:.1f}%)，考虑减少线程数")
        elif cpu_usage < 30:
            print(f"   ✅ CPU使用率较低 ({cpu_usage:.1f}%)，可考虑增加线程数")
        else:
            print(f"   ✅ CPU使用率正常 ({cpu_usage:.1f}%)")

        # 内存建议
        memory_usage = info["memory"]["usage_percent"]
        if memory_usage > 85:
            print(f"   ⚠️  内存使用率过高 ({memory_usage:.1f}%)，建议增加内存或减少并发")
        elif memory_usage < 50:
            print(f"   ✅ 内存使用率健康 ({memory_usage:.1f}%)")
        else:
            print(f"   ✅ 内存使用率正常 ({memory_usage:.1f}%)")

        # 磁盘建议
        disk_usage = info["disk"]["usage_percent"]
        if disk_usage > 90:
            print(f"   ⚠️  磁盘空间不足 ({disk_usage:.1f}%)，建议清理空间")
        else:
            print(f"   ✅ 磁盘空间充足 ({100 - disk_usage:.1f}% 可用)")

    def monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                info = self.get_system_info()

                # 保存数据
                if self.save_to_file:
                    self.performance_data.append(info)

                # 打印状态
                self.print_system_status(info)

                # 等待下一次检查
                time.sleep(self.log_interval)

            except Exception as e:
                print(f"❌ 监控异常: {e}")
                time.sleep(self.log_interval)

    def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            print("⚠️  监控已在运行中...")
            return

        print("🚀 开始系统性能监控...")
        print(f"   - 监控间隔: {self.log_interval} 秒")
        print(f"   - 保存日志: {'是' if self.save_to_file else '否'}")

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        # 打印初始系统信息
        initial_info = self.get_system_info()
        print(f"\n🖥️  系统配置:")
        print(
            f"   CPU: {initial_info['cpu']['count_physical']}核{initial_info['cpu']['count_logical']}线程"
        )
        print(f"   内存: {initial_info['memory']['total_gb']} GB")
        print(f"   磁盘: {initial_info['disk']['total_gb']} GB")

    def stop_monitoring(self):
        """停止监控"""
        if not self.monitoring:
            print("⚠️  监控未在运行...")
            return

        print("🛑 停止系统性能监控...")
        self.monitoring = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)

        # 保存性能数据
        if self.save_to_file and self.performance_data:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"system_performance_{timestamp}.json"

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "monitoring_duration_seconds": len(self.performance_data)
                        * self.log_interval,
                        "data_points": len(self.performance_data),
                        "performance_data": self.performance_data,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            print(f"📊 性能数据已保存到: {filename}")

            # 生成摘要报告
            self.generate_summary_report()

    def generate_summary_report(self):
        """生成性能摘要报告"""
        if not self.performance_data:
            return

        # 计算平均值和峰值
        cpu_values = [d["cpu"]["usage_percent"] for d in self.performance_data]
        memory_values = [d["memory"]["usage_percent"] for d in self.performance_data]

        summary = {
            "cpu": {
                "avg_usage": round(sum(cpu_values) / len(cpu_values), 2),
                "max_usage": round(max(cpu_values), 2),
                "min_usage": round(min(cpu_values), 2),
            },
            "memory": {
                "avg_usage": round(sum(memory_values) / len(memory_values), 2),
                "max_usage": round(max(memory_values), 2),
                "min_usage": round(min(memory_values), 2),
            },
            "recommendations": [],
        }

        # 生成建议
        if summary["cpu"]["avg_usage"] > 80:
            summary["recommendations"].append("CPU平均使用率过高，建议减少并发线程数")
        elif summary["cpu"]["avg_usage"] < 40:
            summary["recommendations"].append("CPU平均使用率较低，可以增加并发线程数提升效率")

        if summary["memory"]["avg_usage"] > 80:
            summary["recommendations"].append("内存使用率过高，建议增加内存或优化内存使用")

        print(f"\n📈 性能摘要报告:")
        print(
            f"   CPU平均使用率: {summary['cpu']['avg_usage']}% (峰值: {summary['cpu']['max_usage']}%)"
        )
        print(
            f"   内存平均使用率: {summary['memory']['avg_usage']}% (峰值: {summary['memory']['max_usage']}%)"
        )

        if summary["recommendations"]:
            print(f"   建议:")
            for rec in summary["recommendations"]:
                print(f"     - {rec}")


def main():
    """主函数 - 提供交互式监控"""
    monitor = SystemMonitor(log_interval=3, save_to_file=True)

    print("🖥️  系统性能监控器")
    print("=" * 50)
    print("用于监控WFA回测期间的系统资源使用情况")
    print("帮助优化硬件配置和线程数设置")
    print("=" * 50)

    try:
        print("\n按任意键开始监控 (Ctrl+C 停止)...")
        input()

        monitor.start_monitoring()

        # 保持程序运行，直到用户按Ctrl+C
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 用户中断监控...")
        monitor.stop_monitoring()
        print("✅ 监控已停止")


if __name__ == "__main__":
    main()
