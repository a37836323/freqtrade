@echo off
chcp 65001 >nul
echo.
echo ================================================
echo   前向分析 (WFA) 策略评测器 V3.0 - 多线程优化版
echo   Strategy_Simple_Indicator_Test 专用
echo   🚀 多线程并行回测 + 智能资源管理
echo ================================================
echo.
echo 🚀 V3.0 多线程新特性：
echo    ⚡ 并行回测：根据CPU核心数自动调整线程数
echo    📊 智能资源管理：避免系统过载
echo    🎯 任务队列：合理分配回测任务
echo    💾 内存优化：减少重复加载
echo    🔧 线程安全：确保数据一致性
echo.
echo 💻 性能优化建议：
echo    - CPU: 多核处理器（推荐16核+）
echo    - 内存: 32GB+ （避免内存不足）
echo    - 存储: NVMe SSD （提升数据读写速度）
echo    - Python: 使用Anaconda环境
echo.
echo 📈 预期加速效果：
echo    - 4核CPU: 约3倍加速
echo    - 8核CPU: 约6倍加速  
echo    - 16核CPU: 约12倍加速
echo    - 32核CPU: 约24倍加速
echo.

echo 🔧 检测系统配置...
echo CPU核心数: %NUMBER_OF_PROCESSORS%

if %NUMBER_OF_PROCESSORS% LSS 4 (
    echo.
    echo ⚠️  警告: 您的CPU核心数较少，建议升级硬件以获得更好性能
    echo.
)

if %NUMBER_OF_PROCESSORS% GEQ 8 (
    echo.
    echo ✅ 您的CPU配置良好，适合多线程回测
    echo.
)

pause

echo.
echo ⏳ 正在启动多线程WFA评测器V3.0...
echo.

python WFA_Strategy_Evaluator_V3_MultiThread.py

echo.
echo 🎉 多线程WFA评测V3.0完成！
echo.
echo 📝 请查看生成的报告文件：
echo    - wfa_evaluation_v3_multithread_*.log (详细日志)
echo    - wfa_results_v3_multithread_*.json (完整结果)
echo    - wfa_config_v3.json (配置文件)
echo.
echo 🚀 V3.0 多线程优势：
echo    ✅ 大幅提升回测速度（根据CPU核心数）
echo    ✅ 智能资源管理，避免系统卡死
echo    ✅ 实时进度显示，了解测试状态
echo    ✅ 线程安全设计，确保结果准确
echo    ✅ 自动配置优化，开箱即用
echo.

pause
