@echo off
echo 设置代理环境变量...

:: 设置HTTP和HTTPS代理
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890

:: 输出确认信息
echo 环境变量已设置:
echo HTTP_PROXY=%HTTP_PROXY%
echo HTTPS_PROXY=%HTTPS_PROXY%

:: 激活虚拟环境（如果有）
if exist .venv\Scripts\activate.bat (
    echo 正在激活虚拟环境...
    call .venv\Scripts\activate.bat
)

:: 检查虚拟环境是否成功激活
if %ERRORLEVEL% neq 0 (
    echo 虚拟环境激活失败或不存在！继续执行...
)

echo 正在启动 FreqTrade 交易...

:: 启动FreqTrade交易


::freqtrade backtesting   -c ./user_data/config.json  --strategy  Strategy_Simple_Indicator_Test --timeframe 30m   --timeframe-detail 5m  --timerange=20210111-20210720 --breakdown day week month  --logfile ./huice1.log 
freqtrade backtesting   -c ./user_data/config.json  --strategy  Strategy_Simple_Indicator_Test --timeframe 30m   --timeframe-detail 5m  --timerange=20231111-20241111 --breakdown day week month  --logfile ./huice1.log 


:: 检查FreqTrade运行结果
if %ERRORLEVEL% neq 0 (
    echo FreqTrade 运行出错！
    pause
) else (
    echo FreqTrade 运行完成！
)

:: 如果之前激活了虚拟环境，则取消激活
if defined VIRTUAL_ENV (
    call deactivate
)

pause