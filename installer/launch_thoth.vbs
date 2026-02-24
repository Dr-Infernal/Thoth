' Thoth silent launcher – runs launch_thoth.bat with no visible console window
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run Chr(34) & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\launch_thoth.bat" & Chr(34), 0, False
