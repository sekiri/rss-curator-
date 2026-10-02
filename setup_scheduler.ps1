<#
.SYNOPSIS
    RSS Curator - Windows タスクスケジューラ登録・解除スクリプト
.DESCRIPTION
    毎日の自動キュレーション＆GitHubプッシュタスクを Windows タスクスケジューラに登録または削除します。
.PARAMETER Time
    毎日実行する時刻（デフォルト: "07:00"）
.PARAMETER TaskName
    登録するタスクの名前（デフォルト: "RSS-Curator-DailyUpdate"）
.PARAMETER Remove
    指定すると登録済みタスクを削除します。
.PARAMETER Status
    指定すると現在の登録状況を表示します。
.EXAMPLE
    .\setup_scheduler.ps1
    （毎朝 07:00 に自動実行するタスクを登録）
.EXAMPLE
    .\setup_scheduler.ps1 -Time "08:30"
    （毎朝 08:30 に自動実行するタスクを登録）
.EXAMPLE
    .\setup_scheduler.ps1 -Status
    （現在のタスク登録状態を確認）
.EXAMPLE
    .\setup_scheduler.ps1 -Remove
    （登録済みタスクを削除）
#>

param(
    [string]$Time = "07:00",
    [string]$TaskName = "RSS-Curator-DailyUpdate",
    [switch]$Remove,
    [switch]$Status
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = $PSScriptRoot
$vbsPath = Join-Path $scriptDir "run_silent.vbs"

# 状態確認
if ($Status) {
    Write-Host "--- タスク状態確認: $TaskName ---" -ForegroundColor Cyan
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "状態: 登録済み" -ForegroundColor Green
        Write-Host "有効フラグ: $($task.Settings.Enabled)"
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "前回実行: $($info.LastRunTime) (結果: $($info.LastTaskResult))"
        Write-Host "次回実行: $($info.NextRunTime)"
    } else {
        Write-Host "状態: 未登録（タスクが存在しません）" -ForegroundColor Yellow
    }
    return
}

# タスク削除
if ($Remove) {
    Write-Host "タスク '$TaskName' を削除しています..." -ForegroundColor Yellow
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
        Write-Host "タスク '$TaskName' を正常に削除しました。" -ForegroundColor Green
    } catch {
        Write-Host "削除対象のタスクが見つかりませんでした。" -ForegroundColor Red
    }
    return
}

# タスク登録
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   RSS Curator - Windows タスクスケジューラ登録" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "実行時刻: 毎日 $Time" -ForegroundColor Yellow
Write-Host "実行対象: $vbsPath (画面表示なしでバックグラウンド実行)" -ForegroundColor Yellow
Write-Host ""

if (-not (Test-Path $vbsPath)) {
    Write-Host "[エラー] $vbsPath が見つかりません。" -ForegroundColor Red
    exit 1
}

try {
    # アクション定義（wscript.exe で run_silent.vbs を実行）
    $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbsPath`"" -WorkingDirectory $scriptDir

    # トリガー定義（毎日指定時刻）
    $trigger = New-ScheduledTaskTrigger -Daily -At $Time

    # 設定（スリープ復帰時にも遅延実行する、バッテリ駆動時でも実行する等）
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    # タスクの登録（現在のユーザー権限で実行）
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "RSS Curator Autonomous Update and GitHub Push" -Force | Out-Null

    Write-Host "========================================================" -ForegroundColor Green
    Write-Host " [成功] タスクスケジューラへの登録が完了しました！" -ForegroundColor Green
    Write-Host " 毎日 $Time にバックグラウンドで自動実行され、" -ForegroundColor Green
    Write-Host " 最新の関心記事が Feedly に配信されます。" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "・動作確認や状態確認: .\setup_scheduler.ps1 -Status" -ForegroundColor Gray
    Write-Host "・自動実行の解除:     .\setup_scheduler.ps1 -Remove" -ForegroundColor Gray
} catch {
    Write-Host "[エラー] タスクの登録に失敗しました: $_" -ForegroundColor Red
    Write-Host "※管理者権限の PowerShell で実行してください。" -ForegroundColor Yellow
    exit 1
}
