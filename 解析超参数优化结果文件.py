import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple


# 直接使用 Freqtrade 的内部模块
try:
    from freqtrade.data.btanalysis import get_latest_hyperopt_file
    from freqtrade.optimize.hyperopt_tools import HyperoptTools
except ImportError as e:
    print(f"导入 Freqtrade 模块失败: {e}")
    print("请确保在 Freqtrade 环境中运行此脚本")
    exit(1)


def load_hyperopt_results_direct(
    hyperopt_filename: str = None,
    user_data_dir: str = "user_data",
    only_best: bool = False,
    only_profitable: bool = False,
    min_trades: int = 0,
    max_trades: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    直接使用 Freqtrade 内部 API 加载超参数优化结果

    Parameters:
    - hyperopt_filename: 指定的超参数文件名，如果为 None 则使用最新的
    - user_data_dir: 用户数据目录
    - only_best: 只返回最佳结果
    - only_profitable: 只返回盈利的结果
    - min_trades: 最小交易数过滤
    - max_trades: 最大交易数过滤

    Returns:
    - (epochs_list, total_epochs): 过滤后的 epoch 列表和总 epoch 数
    """

    # 构建超参数结果目录路径
    hyperopt_results_dir = Path(user_data_dir) / "hyperopt_results"

    if not hyperopt_results_dir.exists():
        print(f"超参数结果目录不存在: {hyperopt_results_dir}")
        return [], 0

    # 获取超参数结果文件
    if hyperopt_filename:
        # 检查是否为绝对路径或相对路径
        hyperopt_path = Path(hyperopt_filename)
        if hyperopt_path.is_absolute() or hyperopt_path.exists():
            # 如果是绝对路径或文件存在，直接使用
            results_file = hyperopt_path
        else:
            # 否则，拼接到超参数结果目录
            results_file = hyperopt_results_dir / hyperopt_filename

        if not results_file.exists():
            print(f"指定的超参数文件不存在: {results_file}")
            return [], 0
    else:
        try:
            results_file = get_latest_hyperopt_file(hyperopt_results_dir, None)
        except Exception as e:
            print(f"获取最新超参数文件失败: {e}")
            return [], 0

    print(f"加载超参数结果文件: {results_file}")

    # 构建过滤配置
    config = {
        "hyperopt_list_best": only_best,
        "hyperopt_list_profitable": only_profitable,
        "hyperopt_list_min_trades": min_trades,
        "hyperopt_list_max_trades": max_trades,
        "hyperopt_list_min_avg_time": None,
        "hyperopt_list_max_avg_time": None,
        "hyperopt_list_min_avg_profit": None,
        "hyperopt_list_max_avg_profit": None,
        "hyperopt_list_min_total_profit": None,
        "hyperopt_list_max_total_profit": None,
        "hyperopt_list_min_objective": None,
        "hyperopt_list_max_objective": None,
    }

    # 使用 Freqtrade 的内部方法加载和过滤结果
    try:
        epochs, total_epochs = HyperoptTools.load_filtered_results(results_file, config)
        print(f"成功加载 {len(epochs)} 个过滤后的 epoch（总共 {total_epochs} 个）")
        return epochs, total_epochs
    except Exception as e:
        print(f"加载超参数结果失败: {e}")
        return [], 0


def get_top_params_direct(
    top_n: int = 10,
    hyperopt_filename: str = None,
    user_data_dir: str = "user_data",
    sort_by: str = "loss",  # "loss", "profit", "sharpe", "trades"
    only_best: bool = False,  # 只选择标记为"Best"的结果
) -> List[Dict[str, Any]]:
    """
    直接从 .fthypt 文件获取前N个最佳参数组合

    Parameters:
    - top_n: 返回前N个结果
    - hyperopt_filename: 超参数文件名
    - user_data_dir: 用户数据目录
    - sort_by: 排序依据 ("loss", "profit", "sharpe", "trades")

    Returns:
    - 参数组合列表
    """

    # 加载所有结果
    epochs, total_epochs = load_hyperopt_results_direct(
        hyperopt_filename=hyperopt_filename, user_data_dir=user_data_dir, only_best=only_best
    )

    if not epochs:
        print("没有找到有效的超参数结果")
        return []

    if only_best:
        print(f"[INFO] 只选择标记为'Best'的结果，共找到 {len(epochs)} 个")

    # 根据指定字段排序
    if sort_by == "loss":
        # loss 越小越好
        sorted_epochs = sorted(epochs, key=lambda x: x.get("loss", float("inf")))
    elif sort_by == "profit":
        # profit 越大越好
        sorted_epochs = sorted(
            epochs,
            key=lambda x: -x.get("results_metrics", {}).get("profit_total_abs", float("-inf")),
        )
    elif sort_by == "sharpe":
        # sharpe 越大越好
        sorted_epochs = sorted(
            epochs, key=lambda x: -x.get("results_metrics", {}).get("sharpe", float("-inf"))
        )
    elif sort_by == "trades":
        # 交易数量越多越好（在一定范围内）
        sorted_epochs = sorted(
            epochs, key=lambda x: -x.get("results_metrics", {}).get("total_trades", 0)
        )
    else:
        print(f"不支持的排序字段: {sort_by}")
        sorted_epochs = epochs

    # 获取前N个结果
    top_epochs = sorted_epochs[:top_n]

    # 提取和格式化参数
    param_sets = []
    for i, epoch in enumerate(top_epochs):
        try:
            # 从 epoch 中提取参数详情
            params_details = epoch.get("params_details", {})
            params_not_optimized = epoch.get("params_not_optimized", {})
            results_metrics = epoch.get("results_metrics", {})

            # 合并优化和非优化参数
            all_params = {
                "buy_params": params_details.get("buy", {}),
                "sell_params": params_details.get("sell", {}),
                "roi_params": params_details.get("roi", {}),
                "stoploss_params": params_details.get("stoploss", {}),
                "trailing_params": params_details.get("trailing", {}),
                "protection_params": params_details.get("protection", {}),
                "max_open_trades": params_details.get("max_open_trades", {}),
            }

            # 添加非优化参数
            for space, space_params in params_not_optimized.items():
                if space in all_params:
                    all_params[space].update(space_params)
                else:
                    all_params[space] = space_params

            # 提取性能指标
            metrics = {
                "loss": epoch.get("loss", 0),
                "profit_total_abs": results_metrics.get("profit_total_abs", 0),
                "profit_total_percent": results_metrics.get("profit_total", 0),
                "total_trades": results_metrics.get("total_trades", 0),
                "sharpe": results_metrics.get("sharpe", 0),
                "calmar": results_metrics.get("calmar", 0),
                "sortino": results_metrics.get("sortino", 0),
                "max_drawdown": results_metrics.get("max_drawdown", 0),
                "win_rate": results_metrics.get("wins", 0)
                / max(results_metrics.get("total_trades", 1), 1),
                "avg_profit": results_metrics.get("profit_mean", 0),
                "stake_currency": results_metrics.get("stake_currency", "USDT"),
            }

            param_sets.append(
                {
                    "rank": i + 1,
                    "epoch": epoch.get("current_epoch", i + 1),
                    "is_best": epoch.get("is_best", False),
                    "is_initial_point": epoch.get("is_initial_point", False),
                    "params": all_params,
                    "metrics": metrics,
                    "backtest_start_time": epoch.get("backtest_start_time"),
                    "backtest_end_time": epoch.get("backtest_end_time"),
                }
            )

        except Exception as e:
            print(f"处理第 {i + 1} 个结果时出错: {e}")
            continue

    return param_sets


def print_params_summary(param_sets: List[Dict[str, Any]], detailed: bool = False):
    """
    打印参数摘要

    Parameters:
    - param_sets: 参数组合列表
    - detailed: 是否显示详细信息
    """
    if not param_sets:
        print("没有参数可显示")
        return

    print(f"\n{'=' * 80}")
    print(f"超参数优化结果摘要 - 共 {len(param_sets)} 组参数")
    print(f"{'=' * 80}")

    for param_set in param_sets:
        rank = param_set["rank"]
        epoch = param_set["epoch"]
        metrics = param_set["metrics"]
        params = param_set["params"]

        print(f"\n[RANK] 排名 #{rank} (Epoch {epoch})")
        print(f"   {'[BEST] 最佳结果' if param_set['is_best'] else ''}")
        print(f"   Loss: {metrics['loss']:.6f}")
        print(
            f"   总收益: {metrics['profit_total_abs']:.2f} {metrics['stake_currency']} ({metrics['profit_total_percent']:.2f}%)"
        )
        print(f"   交易次数: {metrics['total_trades']}")
        print(f"   胜率: {metrics['win_rate']:.2%}")
        print(f"   夏普比率: {metrics['sharpe']:.3f}")
        print(f"   最大回撤: {metrics['max_drawdown']:.2%}")

        if detailed:
            print(f"\n   [PARAMS] 详细参数:")
            for param_type, param_values in params.items():
                if param_values:  # 只显示非空参数
                    print(f"   {param_type}:")
                    for key, value in param_values.items():
                        print(f"     {key}: {value}")

        print(f"   {'-' * 60}")


def export_best_params_to_json(
    param_sets: List[Dict[str, Any]], output_file: str = "best_hyperopt_params.json", top_n: int = 5
):
    """
    导出最佳参数到 JSON 文件

    Parameters:
    - param_sets: 参数组合列表
    - output_file: 输出文件名
    - top_n: 导出前N个结果
    """
    if not param_sets:
        print("没有参数可导出")
        return

    export_data = {
        "export_time": str(Path().cwd()),
        "total_results": len(param_sets),
        "exported_count": min(top_n, len(param_sets)),
        "best_params": param_sets[:top_n],
    }

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n[SUCCESS] 成功导出前 {min(top_n, len(param_sets))} 个最佳参数到: {output_file}")
    except Exception as e:
        print(f"[ERROR] 导出参数失败: {e}")


# 使用示例
if __name__ == "__main__":
    print("[INFO] 开始解析超参数优化结果...")

    # 获取前20个最佳参数（按 loss 排序）
    top_params = get_top_params_direct(
        top_n=20,
        hyperopt_filename=None,  # 使用最新文件
        user_data_dir="user_data",
        sort_by="loss",  # 可选: "loss", "profit", "sharpe", "trades"
        only_best=True,
    )

    if top_params:
        # 打印摘要
        print_params_summary(top_params, detailed=True)

        # 导出到 JSON
        export_best_params_to_json(top_params, "best_hyperopt_params.json", 5)

        # 单独显示最佳参数的买入和卖出参数
        best_params = top_params[0]
        print(f"\n[BEST] 最佳参数组合 (Epoch {best_params['epoch']}):")
        print(f"买入参数:")
        print(json.dumps(best_params["params"]["buy_params"], indent=2, ensure_ascii=False))
        print(f"\n卖出参数:")
        print(json.dumps(best_params["params"]["sell_params"], indent=2, ensure_ascii=False))

    else:
        print("[ERROR] 没有找到有效的超参数结果")
