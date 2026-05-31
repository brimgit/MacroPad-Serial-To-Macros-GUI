Dim scriptDir, pythonw, script
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pythonw = "C:\Users\dewin\AppData\Local\Programs\Python\Python313\pythonw.exe"
script = scriptDir & "\MacroPad.pyw"
CreateObject("WScript.Shell").Run """" & pythonw & """ """ & script & """", 0, False
