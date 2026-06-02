Dim scriptDir, exe
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
exe = scriptDir & "\dist\MacroPad\MacroPad.exe"
CreateObject("WScript.Shell").Run """" & exe & """", 0, False
