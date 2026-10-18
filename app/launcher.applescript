set home to POSIX path of (path to home folder)
set py to home & "Downloads/Claude/Projects/AIe/G-Micro/.venv/bin/python"
set srv to home & "Downloads/Claude/Projects/AIe/G-Dev/app/server.py"
try
	do shell script "curl -sf -m 2 http://localhost:8615/api/status"
on error
	do shell script "nohup " & quoted form of py & " " & quoted form of srv & " 8615 > /tmp/g-dev-panel.log 2>&1 &"
	repeat 120 times
		delay 1
		try
			do shell script "curl -sf -m 2 http://localhost:8615/api/status"
			exit repeat
		end try
	end repeat
end try
open location "http://localhost:8615"
