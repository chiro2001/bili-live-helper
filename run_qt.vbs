DIM objShell
set objShell=wscript.createObject("wscript.shell")
iReturn=objShell.Run("cmd /C python run_qt.py", 0, TRUE)