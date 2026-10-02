<#
.SYNOPSIS
    RSS Curator - 手動更新 & GitHub プッシュ スクリプト
.DESCRIPTION
    フィードの巡回、ブックマークとの類似度計算、XML生成、GitHubへの自動プッシュを一括実行します。
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   RSS Curator - 手動更新 & GitHub プッシュ" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

try {
    Write-Host "[実行中] 巡回・スコアリング・XML生成・GitHubプッシュ..." -ForegroundColor Yellow
    uv run python -m src.main --run --push

    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host "   [完了] フィードの更新とGitHubプッシュが完了しました！" -ForegroundColor Green
    Write-Host "   Feedly等のリーダーで1〜2分後に最新記事が反映されます。" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Red
    Write-Host "   [エラー] 更新処理中にエラーが発生しました: $_" -ForegroundColor Red
    Write-Host "========================================================" -ForegroundColor Red
    exit 1
}
