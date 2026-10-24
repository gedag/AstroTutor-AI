' run_instruction_loop.py'yi gizli pencerede başlatır (Windows Görev Zamanlayıcı için).
' Proje kökü bu dosyanın konumundan bulunur; çıktı logs\loop_task.out dosyasına eklenir.
' Kurulum ve kaldırma: README.md -> "Instruction üretimini arka planda sürdürme (Windows)".
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName)))
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = root
cmd = "cmd /c set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& " & _
      """" & root & "\.venv\Scripts\python.exe"" """ & root & "\run_instruction_loop.py"" >> """ & _
      root & "\logs\loop_task.out"" 2>&1"
sh.Run cmd, 0, False
