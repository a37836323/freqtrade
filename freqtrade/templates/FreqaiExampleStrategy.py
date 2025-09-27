import logging
from functools import reduce

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.strategy import IStrategy


logger = logging.getLogger(__name__)


class FreqaiExampleStrategy(IStrategy):
    """
    示例策略，展示用户如何将自己的 IFreqaiModel 连接到策略中。

    """

    # 高频交易ROI设置 - 快速获利了结
    minimal_roi = {
        "60": 0.0,  # 60分钟后无论盈亏都退出（防止过度持仓）
        "30": 0.005,  # 30分钟后如果有0.5%利润就退出
        "15": 0.01,  # 15分钟后如果有1%利润就退出
        "5": 0.015,  # 5分钟后如果有1.5%利润就退出
        "0": 0.025,  # 立即：如果有2.5%利润就退出
    }

    plot_config = {
        "main_plot": {},  # 主图
        "subplots": {
            "&-s_close": {"&-s_close": {"color": "blue"}},
            "do_predict": {
                "do_predict": {"color": "brown"},
            },
        },
    }

    process_only_new_candles = True  # 仅处理新蜡烛

    # 高频交易追踪止盈 - 适合短期波段
    trailing_stop = True
    trailing_stop_positive = 0.015  # 盈利时的追踪止损：1.5%
    trailing_stop_positive_offset = 0.02  # 盈利达到2%时启动追踪
    trailing_only_offset_is_reached = True  # 只有达到2%盈利才启动追踪

    stoploss = -0.025  # 2.5%止损（适合高频交易，防止大幅亏损）

    use_exit_signal = True  # 使用退出信号
    # 这是传递给 talib 的最大周期（与时间框架无关）
    startup_candle_count: int = 60  # 传递给 talib 的最大周期，确保足够计算VWMA-50
    can_short = True  # 可以做空

    def calculate_vwma(self, dataframe: DataFrame, length: int = 14):
        """
        计算 VWMA (Volume Weighted Moving Average - 成交量加权移动平均线)

        VWMA公式：
        VWMA = SUM(Price * Volume, length) / SUM(Volume, length)

        参数:
        - dataframe: 包含price和volume的DataFrame
        - length: 计算周期

        返回:
        - DataFrame: 包含VWMA值的Series
        """
        try:
            # 使用HLC3作为价格源（高点+低点+收盘价）/3
            hlc3 = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3

            # 计算VWMA
            # 分子：价格*成交量的滚动求和
            numerator = (hlc3 * dataframe["volume"]).rolling(window=length, min_periods=1).sum()
            # 分母：成交量的滚动求和
            denominator = dataframe["volume"].rolling(window=length, min_periods=1).sum()

            # 防止除零错误
            vwma = numerator / denominator.replace(0, np.nan)

            # 处理NaN值：如果成交量为0，使用简单移动平均作为备选
            sma_fallback = hlc3.rolling(window=length, min_periods=1).mean()
            vwma = vwma.fillna(sma_fallback)

            return vwma

        except Exception as e:
            logger.warning(f"VWMA计算失败: {e}, 使用SMA作为备选方案")
            # 备选方案：使用简单移动平均
            hlc3 = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3
            return hlc3.rolling(window=length, min_periods=1).mean()

    def feature_engineering_expand_all(
        self, dataframe: DataFrame, period: int, metadata: dict, **kwargs
    ) -> DataFrame:
        """
        # 仅在启用 FreqAI 的策略中有效
        # 本函数会根据配置文件中的 `indicator_periods_candles`、`include_timeframes`、`include_shifted_candles` 和
        # `include_corr_pairs` 自动扩展这里定义的特征。换句话说，在本函数中定义的单个特征，最终会自动扩展为
        # `indicator_periods_candles` * `include_timeframes` * `include_shifted_candles` * `include_corr_pairs` 个特征，添加到模型中。
        #
        # 所有特征列名必须以 `%` 开头，以便被 FreqAI 内部识别。
        #
        # 可以通过如下方式访问元数据（如当前交易对和时间周期）：
        # metadata["pair"]  metadata["tf"]
        #
        # 更多关于这些配置参数如何加速特征工程的信息，请参考文档：
        # https://www.freqtrade.io/zh_CN/latest/freqai-parameter-table/#feature-parameters
        # https://www.freqtrade.io/zh_CN/latest/freqai-feature-engineering/#defining-the-features
        #
        # :param dataframe: 将接收特征的策略 dataframe
        # :param period: 指标的周期 - 用法示例：
        # :param metadata: 当前交易对的元数据
        # dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)
        """

        dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe["%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        dataframe["%-adx-period"] = ta.ADX(dataframe, timeperiod=period)
        dataframe["%-sma-period"] = ta.SMA(dataframe, timeperiod=period)
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)

        # 高频交易关键指标
        # Williams %R - 快速动量指标，适合捕捉超买超卖
        dataframe["%-willr-period"] = ta.WILLR(dataframe, timeperiod=period)
        # CCI - 商品通道指数，识别趋势变化
        dataframe["%-cci-period"] = ta.CCI(dataframe, timeperiod=period)
        # ATR - 真实波动幅度，衡量市场波动性
        dataframe["%-atr-period"] = ta.ATR(dataframe, timeperiod=period)
        # Stochastic RSI - 结合随机指标和RSI，更敏感的超买超卖信号
        stoch_rsi = ta.STOCHRSI(dataframe, timeperiod=period)
        dataframe["%-stochrsi_k-period"] = stoch_rsi["fastk"]
        dataframe["%-stochrsi_d-period"] = stoch_rsi["fastd"]

        # 添加VWMA（成交量加权移动平均线）
        dataframe["%-vwma-period"] = self.calculate_vwma(dataframe, length=period)

        # VWMA相关的派生特征
        # 价格相对于VWMA的偏离百分比
        dataframe["%-close-vwma-ratio-period"] = dataframe["close"] / dataframe["%-vwma-period"]
        # VWMA的变化率
        dataframe["%-vwma-change-period"] = dataframe["%-vwma-period"].pct_change()
        # 价格突破VWMA的强度
        dataframe["%-vwma-breakout-strength-period"] = (
            dataframe["close"] - dataframe["%-vwma-period"]
        ) / dataframe["%-atr-period"]

        # 高频动量特征
        # 价格动量 - 当前收盘价与N周期前的比较
        dataframe["%-price-momentum-period"] = (
            dataframe["close"] / dataframe["close"].shift(period) - 1
        )
        # 成交量动量 - 当前成交量与平均成交量的比较
        dataframe["%-volume-momentum-period"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period).mean()
        )
        # ATR标准化的价格变化
        dataframe["%-normalized-change-period"] = dataframe["close"].pct_change() / (
            dataframe["%-atr-period"] / dataframe["close"]
        )

        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=period, stds=2.2
        )
        dataframe["bb_lowerband-period"] = bollinger["lower"]
        dataframe["bb_middleband-period"] = bollinger["mid"]
        dataframe["bb_upperband-period"] = bollinger["upper"]

        # 增强的布林带特征
        dataframe["%-bb_width-period"] = (
            dataframe["bb_upperband-period"] - dataframe["bb_lowerband-period"]
        ) / dataframe["bb_middleband-period"]
        dataframe["%-close-bb_lower-period"] = dataframe["close"] / dataframe["bb_lowerband-period"]
        dataframe["%-close-bb_upper-period"] = dataframe["close"] / dataframe["bb_upperband-period"]
        # BB %B - 价格在布林带中的相对位置
        dataframe["%-bb_percent-period"] = (
            dataframe["close"] - dataframe["bb_lowerband-period"]
        ) / (dataframe["bb_upperband-period"] - dataframe["bb_lowerband-period"])
        # BB宽度变化率 - 波动率是否在增加
        dataframe["%-bb_width_change-period"] = dataframe["%-bb_width-period"].pct_change()
        # BB挤压检测 - 低波动率后的爆发机会
        dataframe["%-bb_squeeze-period"] = (
            dataframe["%-bb_width-period"]
            < dataframe["%-bb_width-period"].rolling(period * 2).quantile(0.2)
        ).astype(int)

        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period)

        dataframe["%-relative_volume-period"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period).mean()
        )

        return dataframe

    def feature_engineering_expand_basic(
        self, dataframe: DataFrame, metadata: dict, **kwargs
    ) -> DataFrame:
        """
        # 仅在启用 FreqAI 的策略中有效
        # 本函数会根据配置文件中的 `include_timeframes`、`include_shifted_candles` 和 `include_corr_pairs`
        # 自动扩展这里定义的特征。换句话说，在本函数中定义的单个特征，最终会自动扩展为
        # `include_timeframes` * `include_shifted_candles` * `include_corr_pairs` 个特征，添加到模型中。
        #
        # 注意：这里定义的特征不会根据用户自定义的 `indicator_periods_candles` 自动复制。
        #
        # 所有特征列名必须以 `%` 开头，以便被 FreqAI 内部识别。
        #
        # 可以通过如下方式访问元数据（如当前交易对和时间周期）：
        # metadata["pair"]  metadata["tf"]
        #
        # 更多关于这些配置参数如何加速特征工程的信息，请参考文档：
        # https://www.freqtrade.io/zh_CN/latest/freqai-parameter-table/#feature-parameters
        # https://www.freqtrade.io/zh_CN/latest/freqai-feature-engineering/#defining-the-features
        #
        # :param dataframe: 将接收特征的策略 dataframe
        # :param metadata: 当前交易对的元数据
        # 用法示例：
        # dataframe["%-pct-change"] = dataframe["close"].pct_change()
        # dataframe["%-ema-200"] = ta.EMA(dataframe, timeperiod=200)
        """
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]

        # 添加固定周期的VWMA特征
        # 短期VWMA（14周期）
        dataframe["%-vwma-14"] = self.calculate_vwma(dataframe, length=14)
        # 中期VWMA（21周期）
        dataframe["%-vwma-21"] = self.calculate_vwma(dataframe, length=21)
        # 长期VWMA（50周期）
        dataframe["%-vwma-50"] = self.calculate_vwma(dataframe, length=50)

        # VWMA交叉信号特征
        # 短期VWMA相对于中期VWMA的位置
        dataframe["%-vwma-14-21-ratio"] = dataframe["%-vwma-14"] / dataframe["%-vwma-21"]
        # 中期VWMA相对于长期VWMA的位置
        dataframe["%-vwma-21-50-ratio"] = dataframe["%-vwma-21"] / dataframe["%-vwma-50"]

        # 高频交易基础特征
        # 快速RSI (3周期) - 捕捉快速超买超卖
        dataframe["%-rsi-3"] = ta.RSI(dataframe, timeperiod=3)
        # 极短期动量 - 1根K线的变化
        dataframe["%-momentum-1"] = dataframe["close"].pct_change(1)
        # 极短期动量 - 2根K线的变化
        dataframe["%-momentum-2"] = dataframe["close"].pct_change(2)
        # K线实体大小 - 衡量价格变化强度
        dataframe["%-candle-body"] = abs(dataframe["close"] - dataframe["open"]) / dataframe["open"]
        # 上影线大小 - 衡量抛压
        dataframe["%-upper-shadow"] = (
            dataframe["high"] - dataframe[["open", "close"]].max(axis=1)
        ) / dataframe["open"]
        # 下影线大小 - 衡量支撑
        dataframe["%-lower-shadow"] = (
            dataframe[["open", "close"]].min(axis=1) - dataframe["low"]
        ) / dataframe["open"]
        # 成交量价格趋势 (VPT) - 成交量确认的价格趋势
        dataframe["%-vpt"] = (dataframe["close"].pct_change() * dataframe["volume"]).cumsum()
        # 成交量标准化 - 相对于近期平均成交量
        dataframe["%-volume-norm"] = dataframe["volume"] / dataframe["volume"].rolling(20).mean()

        return dataframe

    def feature_engineering_standard(
        self, dataframe: DataFrame, metadata: dict, **kwargs
    ) -> DataFrame:
        """
        # 仅在启用 FreqAI 的策略中有效
        # 这是一个可选函数，只会在基础时间周期（base timeframe）的 dataframe 上调用一次。
        # 这是最后被调用的特征工程函数，这意味着传入本函数的 dataframe 已包含所有其他
        # freqai_feature_engineering_* 函数创建的特征和列。
        #
        # 该函数适合进行自定义的复杂特征提取（例如 tsfresh）。
        # 也适合添加不希望被自动扩展的特征（例如星期几）。
        #
        # 所有特征列名必须以 `%` 开头，以便被 FreqAI 内部识别。
        #
        # 可以通过如下方式访问元数据（如当前交易对）：
        # metadata["pair"]
        #
        # 有关特征工程的更多信息，请参见：
        # https://www.freqtrade.io/zh_CN/latest/freqai-feature-engineering
        #
        # :param dataframe: 将接收特征的策略 dataframe
        # :param metadata: 当前交易对的元数据
        # 用法示例：dataframe["%-day_of_week"] = (dataframe["date"].dt.dayofweek + 1) / 7
        """
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        高频波段交易的多目标标签设计

        设计多个目标来捕捉不同的市场机会：
        1. 短期价格变化 - 用于快速进出
        2. 波段幅度预测 - 用于止盈设置
        3. 趋势强度 - 用于持仓决策
        4. 风险评估 - 用于风险控制
        """

        # 获取标签周期
        label_period = self.freqai_info["feature_parameters"]["label_period_candles"]

        # 目标1：短期价格变化 (原有的，但优化计算方式)
        # 使用未来最高价和最低价的中位数，更稳定
        future_high = dataframe["high"].shift(-label_period).rolling(label_period).max()
        future_low = dataframe["low"].shift(-label_period).rolling(label_period).min()
        future_mid = (future_high + future_low) / 2
        dataframe["&-price_change"] = (future_mid / dataframe["close"]) - 1

        # 目标2：波段幅度预测 - 预测未来N根K线的最大波动幅度
        future_range = (future_high - future_low) / dataframe["close"]
        dataframe["&-volatility_range"] = future_range

        # 目标3：趋势强度 - 判断是否存在明确的趋势
        # 计算未来收盘价相对于当前价格的累计变化
        future_close = dataframe["close"].shift(-label_period)
        price_path = []
        for i in range(1, label_period + 1):
            shifted_close = dataframe["close"].shift(-i)
            price_path.append((shifted_close / dataframe["close"]) - 1)

        # 趋势一致性：所有价格变化是否同方向
        if len(price_path) > 0:
            price_changes = np.column_stack(price_path)
            # 计算趋势一致性（正值表示上涨趋势，负值表示下跌趋势）
            trend_consistency = np.mean(price_changes, axis=1) / (
                np.std(price_changes, axis=1) + 1e-8
            )
            dataframe["&-trend_strength"] = trend_consistency
        else:
            dataframe["&-trend_strength"] = 0

        # 目标4：突破信号 - 是否会突破当前价格区间
        # 计算当前价格区间（基于ATR）
        current_atr = ta.ATR(dataframe, timeperiod=14)
        upper_threshold = dataframe["close"] + current_atr * 1.5
        lower_threshold = dataframe["close"] - current_atr * 1.5

        # 判断未来是否突破
        breakout_up = (future_high > upper_threshold).astype(int)
        breakout_down = (future_low < lower_threshold).astype(int)
        # 编码：0=无突破，1=向上突破，-1=向下突破
        dataframe["&-breakout_signal"] = breakout_up - breakout_down

        # 分类器通常使用字符串作为目标变量进行设置：
        # df['&s-up_or_down'] = np.where( df["close"].shift(-100) >
        #                                 df["close"], 'up', 'down')

        # 如果用户希望使用多个目标，可以通过添加更多以'&'开头的列来实现。
        # 需要注意的是，使用多目标时，需要使用支持多输出的预测模型，
        # 例如 freqai/prediction_models/CatboostRegressorMultiTarget.py，
        # 并在命令行中使用 freqtrade trade --freqaimodel CatboostRegressorMultiTarget

        # df["&-s_range"] = (
        #     df["close"]
        #     .shift(-self.freqai_info["feature_parameters"]["label_period_candles"])
        #     .rolling(self.freqai_info["feature_parameters"]["label_period_candles"])
        #     .max()
        #     -
        #     df["close"]
        #     .shift(-self.freqai_info["feature_parameters"]["label_period_candles"])
        #     .rolling(self.freqai_info["feature_parameters"]["label_period_candles"])
        #     .min()
        # )

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 所有指标必须通过 feature_engineering_*() 函数进行填充

        # 模型将返回用户在 `set_freqai_targets()` 中创建的所有标签
        # （以 & 开头的目标），还会返回是否接受预测的指示，
        # 以及用户在 `set_freqai_targets()` 中为每个训练周期创建的
        # 每个标签的目标均值/标准差。

        dataframe = self.freqai.start(dataframe, metadata, self)

        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """
        高频波段交易入场逻辑 - 基于多目标预测的智能入场

        使用多个预测目标的组合来提高入场精确度：
        1. 价格变化方向
        2. 波动幅度足够大
        3. 趋势强度确认
        4. 突破信号确认
        """

        # 多头入场条件 - 更严格的筛选
        enter_long_conditions = [
            df["do_predict"] == 1,  # 基础预测条件
            df["&-price_change"] > 0.008,  # 预测价格上涨超过0.8%
            df["&-volatility_range"] > 0.015,  # 预测波动幅度足够大(>1.5%)，确保有利润空间
            df["&-trend_strength"] > 0.3,  # 预测上涨趋势强度较强
            (df["&-breakout_signal"] >= 0) | (df["&-breakout_signal"].isna()),  # 无向下突破信号
            # 额外的技术面确认
            df["%-rsi-3"] < 70,  # 短期RSI不超买
            df["%-bb_percent-5"] < 0.8,  # 不在布林带顶部
        ]

        if enter_long_conditions:
            df.loc[
                reduce(lambda x, y: x & y, enter_long_conditions), ["enter_long", "enter_tag"]
            ] = (1, "long_hf_swing")

        # 空头入场条件 - 更严格的筛选
        enter_short_conditions = [
            df["do_predict"] == 1,  # 基础预测条件
            df["&-price_change"] < -0.008,  # 预测价格下跌超过0.8%
            df["&-volatility_range"] > 0.015,  # 预测波动幅度足够大(>1.5%)，确保有利润空间
            df["&-trend_strength"] < -0.3,  # 预测下跌趋势强度较强
            (df["&-breakout_signal"] <= 0) | (df["&-breakout_signal"].isna()),  # 无向上突破信号
            # 额外的技术面确认
            df["%-rsi-3"] > 30,  # 短期RSI不超卖
            df["%-bb_percent-5"] > 0.2,  # 不在布林带底部
        ]

        if enter_short_conditions:
            df.loc[
                reduce(lambda x, y: x & y, enter_short_conditions), ["enter_short", "enter_tag"]
            ] = (1, "short_hf_swing")

        # 突破交易机会 - 利用突破信号
        # 向上突破多头
        breakout_long_conditions = [
            df["do_predict"] == 1,
            df["&-breakout_signal"] > 0,  # 预测向上突破
            df["&-volatility_range"] > 0.02,  # 突破需要足够的波动空间
            df["%-volume-norm"] > 1.2,  # 成交量放大确认突破
        ]

        if breakout_long_conditions:
            df.loc[
                reduce(lambda x, y: x & y, breakout_long_conditions), ["enter_long", "enter_tag"]
            ] = (1, "breakout_long")

        # 向下突破空头
        breakout_short_conditions = [
            df["do_predict"] == 1,
            df["&-breakout_signal"] < 0,  # 预测向下突破
            df["&-volatility_range"] > 0.02,  # 突破需要足够的波动空间
            df["%-volume-norm"] > 1.2,  # 成交量放大确认突破
        ]

        if breakout_short_conditions:
            df.loc[
                reduce(lambda x, y: x & y, breakout_short_conditions), ["enter_short", "enter_tag"]
            ] = (1, "breakout_short")

        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """
        高频波段交易出场逻辑 - 基于多目标预测的智能出场
        """

        # 多头出场条件
        exit_long_conditions = [
            df["do_predict"] == 1,
            (df["&-price_change"] < -0.005)  # 预测价格下跌
            | (df["&-trend_strength"] < -0.2)  # 趋势转弱
            | (df["&-breakout_signal"] < 0),  # 预测向下突破
        ]
        if exit_long_conditions:
            df.loc[reduce(lambda x, y: x & y, exit_long_conditions), "exit_long"] = 1

        # 空头出场条件
        exit_short_conditions = [
            df["do_predict"] == 1,
            (df["&-price_change"] > 0.005)  # 预测价格上涨
            | (df["&-trend_strength"] > 0.2)  # 趋势转强
            | (df["&-breakout_signal"] > 0),  # 预测向上突破
        ]
        if exit_short_conditions:
            df.loc[reduce(lambda x, y: x & y, exit_short_conditions), "exit_short"] = 1

        return df

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time,
        entry_tag,
        side: str,
        **kwargs,
    ) -> bool:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = df.iloc[-1].squeeze()

        if side == "long":
            if rate > (last_candle["close"] * (1 + 0.0025)):
                return False
        else:
            if rate < (last_candle["close"] * (1 - 0.0025)):
                return False

        return True
