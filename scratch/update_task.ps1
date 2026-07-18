$action = New-ScheduledTaskAction -Execute 'cmd' -Argument '/c python "d:\05_Quant\v9 Continuum\scripts\daily_retrain.py" >> "d:\05_Quant\v9 Continuum\logs\retrain_scheduler.log" 2>&1'
Set-ScheduledTask -TaskName 'NowTrading_DailyRetrain' -Action $action
