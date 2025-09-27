@echo off
echo kaishi jihuo...

:: 激活虚拟环境
call .venv\Scripts\activate.bat

:: 检查是否成功激活
if %ERRORLEVEL% neq 0 (
    echo jihuoshibai
    pause
    exit /b %ERRORLEVEL%
)

echo jihuo ok Freqtrade hyperopt...

:: 运行 freqtrade hyperopt 命令
:: 首选：CalmarHyperOptLoss 最适合DCA策略（卡尔玛比率 = 年化收益率 / 最大回撤）
:: 次选：ProfitDrawDownHyperOptLoss


freqtrade hyperopt  -c ./user_data/config.json  --hyperopt-loss MultiMetricHyperOptLoss --strategy Strategyshuangxiangtaoli --timeframe 30m --timeframe-detail 5m  --spaces buy sell trailing  --timerange=20210111-20231111 -e 1000 --job-workers 5  --print-all --analyze-per-epoch
:: 检查 freqtrade 运行结果
if %ERRORLEVEL% neq 0 (
    echo Freqtrade 运行出错！
    pause
) else (
    echo Freqtrade 运行完成！
)

:: 可选：取消激活虚拟环境
call deactivate

pause