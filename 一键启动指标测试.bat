@echo off
chcp 65001 >nul
echo.
echo ================================================
echo        🚀 一键启动指标测试套件
echo     Strategy_Simple_Indicator_Test 专用
echo ================================================
echo.
echo 🎯 本套件包含：
echo    ✅ 简化策略：只保留指标逻辑，30分钟强制平仓
echo    ✅ 多线程WFA：根据CPU自动优化线程数
echo    ✅ 配置优化：自动适配硬件配置
echo    ✅ 性能监控：实时监控系统资源使用
echo.
echo 💡 测试目标：
echo    - 验证VWMA+RSI+MFI指标的预测准确性
echo    - 排除复杂交易策略的影响
echo    - 纯粹测试指标质量
echo.

echo 🔧 步骤1: 检测系统配置并自动优化...
echo.
python config_optimizer.py

if errorlevel 1 (
    echo ❌ 配置优化失败，请检查Python环境
    pause
    exit /b 1
)

echo.
echo ✅ 配置优化完成！
echo.

echo 📋 请选择运行模式：
echo.
echo [1] 自动运行 - 使用优化配置直接开始测试
echo [2] 监控模式 - 开启性能监控后再运行测试  
echo [3] 手动配置 - 手动编辑配置后运行
echo [4] 取消
echo.

set /p choice="请输入选择 (1-4): "

if "%choice%"=="1" goto auto_run
if "%choice%"=="2" goto monitor_mode
if "%choice%"=="3" goto manual_config
if "%choice%"=="4" goto end
goto invalid_choice

:auto_run
echo.
echo 🚀 启动自动测试模式...
echo.
python WFA_Strategy_Evaluator_V3_MultiThread.py
goto results

:monitor_mode
echo.
echo 📊 启动性能监控模式...
echo.
echo 💡 提示：
echo    - 监控窗口将显示实时系统资源使用情况
echo    - 可根据监控结果调整线程数获得最佳性能
echo    - 监控过程中按Ctrl+C停止监控并查看建议
echo.
echo ⏳ 5秒后启动监控，按任意键立即启动...
timeout /t 5 > nul

start "系统性能监控" cmd /k "python system_monitor.py"

echo.
echo ⏳ 等待3秒让监控稳定...
timeout /t 3 > nul

echo 🚀 启动WFA测试...
python WFA_Strategy_Evaluator_V3_MultiThread.py
goto results

:manual_config
echo.
echo 🛠️ 手动配置模式...
echo.
echo 📝 请编辑配置文件: wfa_config_v3.json
echo    - max_workers: 线程数（建议为CPU核心数的75%）
echo    - num_random_combinations: 参数组合数
echo    - search_method: 搜索方法 ("random" 或 "grid")
echo.
echo 按任意键打开配置文件进行编辑...
pause

if exist "wfa_config_v3.json" (
    notepad wfa_config_v3.json
) else (
    echo ❌ 配置文件不存在，请先运行配置优化器
    pause
    exit /b 1
)

echo.
echo 配置完成后按任意键继续...
pause

echo 🚀 启动自定义配置测试...
python WFA_Strategy_Evaluator_V3_MultiThread.py
goto results

:invalid_choice
echo.
echo ❌ 无效选择，请重新运行
pause
exit /b 1

:results
echo.
echo 🎉 测试完成！
echo.
echo 📊 查看结果文件：
echo.
for /f %%i in ('dir /b wfa_results_v3_multithread_*.json 2^>nul') do (
    echo    📄 结果文件: %%i
)
for /f %%i in ('dir /b wfa_evaluation_v3_multithread_*.log 2^>nul') do (
    echo    📝 详细日志: %%i
)
echo.

echo 💡 结果分析建议：
echo    - 查看各窗口的最佳参数是否一致
echo    - 对比IS和OOS期间的表现差异
echo    - 关注胜率和平均利润指标
echo    - 如果指标预测准确率高(>65%)，说明指标有效
echo    - 如果准确率接近50%，说明指标效果一般
echo.

echo 📋 下一步建议：
echo    - 如果指标效果好，可以优化交易策略
echo    - 如果指标效果差，需要改进指标算法
echo    - 可尝试不同的参数范围进行进一步测试
echo.

:end
pause
