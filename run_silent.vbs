' RSS Curator - バックグラウンド非表示実行スクリプト
' コマンドプロンプト画面をポップアップさせずに run_scheduled.bat を実行します。

Set objShell = CreateObject("Wscript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strScriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
strBatPath = """" & strScriptDir & "\run_scheduled.bat"""

' 0 = 非表示ウィンドウ, False = 完了を待たずに終了（またはTrueで完了待ち）
objShell.Run strBatPath, 0, True
