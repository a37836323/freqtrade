# WFA策略评测器 V2 重构版本

## 概述

这是 WFA_Strategy_Evaluator_V2.py 的重构版本，将原来的单一文件（1150行）按职责拆分成多个模块，并集成了 Freqtrade 的参数系统。

## 主要改进

### 1. 模块化设计 ✨
- **data_types.py**: 数据类型定义（WFAWindow, BacktestResult, WFAResult, WFAConfig）
- **freqtrade_parameter_generator.py**: 参数生成器，复用Freqtrade参数系统
- **backtest_executor.py**: 回测执行器，负责单次回测
- **wfa_analyzer.py**: WFA分析器，负责窗口管理和优化
- **result_analyzer.py**: 结果分析器，负责统计分析和报告
- **main.py**: 主入口程序

### 2. 复用Freqtrade参数系统 🔧
- 自动从策略文件中检测参数定义（IntParameter, DecimalParameter, CategoricalParameter）
- 无需手动定义参数空间
- 支持网格搜索和随机搜索
- 参数范围和步长直接从策略中读取

### 3. 职责分离 📋
- 每个模块专注于单一职责
- 代码可读性和可维护性大幅提升
- 便于单元测试和功能扩展

## 使用方法

### 快速开始

```bash
# 进入重构版本目录
cd wfa_v2_refactored

# 运行分析
python main.py
```

### 配置文件

程序会自动加载父目录中的 `wfa_config_v2.json` 配置文件。

### 参数检测

程序会自动检测策略文件中的参数定义：

```python
# 策略中的参数定义会被自动识别
vwma_length = IntParameter(10, 30, default=14, space="buy", optimize=True)
change_percentage = DecimalParameter(0.2, 0.4, default=0.4, decimals=2, space="buy", optimize=True)
trade_direction = CategoricalParameter(["ALL", "LONG", "SHORT"], default="LONG", space="buy", optimize=True)
```

## 文件结构

```
wfa_v2_refactored/
├── __init__.py                          # 模块初始化
├── data_types.py                        # 数据类型定义
├── freqtrade_parameter_generator.py     # Freqtrade参数生成器
├── backtest_executor.py                 # 回测执行器
├── wfa_analyzer.py                      # WFA分析器
├── result_analyzer.py                   # 结果分析器
├── main.py                              # 主入口程序
└── README.md                            # 说明文档
```

## 输出文件

- `wfa_evaluation_refactored_YYYYMMDD_HHMMSS.log` - 详细日志
- `wfa_results_refactored_StrategyName_YYYYMMDD_HHMMSS.json` - JSON结果
- `wfa_windows_summary_refactored_StrategyName_YYYYMMDD_HHMMSS.csv` - CSV摘要

## 技术特点

### 参数生成器优势
1. **自动检测**: 从策略类自动提取参数定义
2. **类型支持**: 支持整数、小数、分类参数
3. **范围自动**: 参数范围从策略定义中读取
4. **网格/随机**: 支持两种参数组合生成方式

### 模块化优势
1. **单一职责**: 每个模块专注特定功能
2. **松耦合**: 模块间依赖关系清晰
3. **可扩展**: 便于添加新功能和修改
4. **可测试**: 每个模块可独立测试

## 与原版对比

| 特性 | 原版V2 | 重构版 |
|------|--------|--------|
| 文件数量 | 1个 (1150行) | 7个模块化文件 |
| 参数定义 | 手动硬编码 | 自动从策略检测 |
| 职责分离 | 混杂在一起 | 清晰分离 |
| 可维护性 | 较差 | 优秀 |
| 扩展性 | 困难 | 容易 |
| 测试性 | 困难 | 容易 |

## 依赖要求

- Python 3.8+
- freqtrade
- numpy
- pandas
- 其他依赖与原版相同
