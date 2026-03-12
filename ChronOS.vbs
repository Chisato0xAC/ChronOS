Option Explicit

' One-window user launcher.
' - Starts server.py in background (hidden)
' - Opens Microsoft Edge in app mode
' - When user closes the app window, stops the server
'
' Implementation note:
' We write a temporary PowerShell script into %TEMP% and run it hidden.
' Then we delete that temp file. This avoids keeping a .ps1 in the repo.
'
Dim shell, fso, root
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)

Dim tempDir, psPath
tempDir = shell.ExpandEnvironmentStrings("%TEMP%")
psPath = tempDir & "\ChronOS-User.temp.ps1"

Dim ps
ps = ""
ps = ps & "param([string]$Root)" & vbCrLf
ps = ps & "$ErrorActionPreference='Stop'" & vbCrLf
ps = ps & "Add-Type -AssemblyName System.Windows.Forms" & vbCrLf
ps = ps & "function Msg([string]$t,[string]$title='ChronOS'){[void][System.Windows.Forms.MessageBox]::Show($t,$title)}" & vbCrLf
ps = ps & "function TestPort([string]$h,[int]$p){try{$c=New-Object Net.Sockets.TcpClient;$iar=$c.BeginConnect($h,$p,$null,$null);$ok=$iar.AsyncWaitHandle.WaitOne(200);if($ok -and $c.Connected){$c.EndConnect($iar)|Out-Null;$c.Close();return $true};$c.Close();$false}catch{$false}}" & vbCrLf
ps = ps & "function FindPy(){if(Get-Command python -EA SilentlyContinue){'python'}elseif(Get-Command py -EA SilentlyContinue){'py'}else{$null}}" & vbCrLf
ps = ps & "function FindEdge(){ $e=Get-Command msedge -EA SilentlyContinue; if($e){return $e.Source}; $pf=$env:ProgramFiles; $pf86=[Environment]::GetEnvironmentVariable('ProgramFiles(x86)'); $c=@(); if($pf){$c+= (Join-Path $pf 'Microsoft\Edge\Application\msedge.exe')}; if($pf86){$c+=(Join-Path $pf86 'Microsoft\Edge\Application\msedge.exe')}; foreach($p in $c){if(Test-Path $p){return $p}}; $null }" & vbCrLf

ps = ps & "$Root=(Resolve-Path $Root).Path" & vbCrLf
ps = ps & "Set-Location $Root" & vbCrLf
ps = ps & "$port=8000" & vbCrLf
ps = ps & "$url='http://127.0.0.1:' + $port + '/'" & vbCrLf

ps = ps & "if(TestPort '127.0.0.1' $port){Msg ('Port ' + $port + ' is already in use.') 'ChronOS - Start Failed'; exit 1}" & vbCrLf
ps = ps & "$py=FindPy; if(-not $py){Msg 'Python not found (python/py).' 'ChronOS - Start Failed'; exit 1}" & vbCrLf
ps = ps & "$edge=FindEdge; if(-not $edge){Msg 'Microsoft Edge not found (msedge.exe).' 'ChronOS - Start Failed'; exit 1}" & vbCrLf

ps = ps & "$logs=Join-Path $Root 'logs'; New-Item -ItemType Directory -Force -Path $logs|Out-Null" & vbCrLf
ps = ps & "$out=Join-Path $logs 'server.out.log'; $err=Join-Path $logs 'server.err.log'" & vbCrLf
ps = ps & "Remove-Item -Force -EA SilentlyContinue $out,$err" & vbCrLf

ps = ps & "$env:PYTHONUTF8='1'" & vbCrLf
ps = ps & "$env:PYTHONIOENCODING='utf-8'" & vbCrLf

ps = ps & "$edgeProfile=Join-Path ([IO.Path]::GetTempPath()) 'ChronOS_edge_profile'; New-Item -ItemType Directory -Force -Path $edgeProfile|Out-Null" & vbCrLf
ps = ps & "$server=$null; $app=$null" & vbCrLf

ps = ps & "try{" & vbCrLf
ps = ps & "  $server=Start-Process -FilePath $py -ArgumentList @('-X','utf8','-u','server.py') -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru" & vbCrLf
ps = ps & "  $ready=$false; for($i=0;$i -lt 50;$i++){Start-Sleep -Milliseconds 200; if(TestPort '127.0.0.1' $port){$ready=$true;break}; if($server.HasExited){break}}" & vbCrLf
ps = ps & "  if(-not $ready){Msg ('Server start failed. Logs: ' + $out + ' ' + $err) 'ChronOS - Start Failed'; exit 1}" & vbCrLf
ps = ps & "  $w=500; $h=360;" & vbCrLf
ps = ps & "  try { $scr=[System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea; $x=[Math]::Max(0,[int](($scr.Width-$w)/2)); $y=[Math]::Max(0,[int](($scr.Height-$h)/2)) } catch { $x=120; $y=80 }" & vbCrLf
ps = ps & "  $pos='--window-position=' + $x + ',' + $y; $size='--window-size=' + $w + ',' + $h;" & vbCrLf
ps = ps & "  $args=@('--app=' + $url, '--user-data-dir=' + $edgeProfile, '--no-first-run', '--disable-sync', '--disable-features=msUndersideButton', $pos, $size)" & vbCrLf
ps = ps & "  $app=Start-Process -FilePath $edge -ArgumentList $args -WorkingDirectory $Root -PassThru" & vbCrLf
ps = ps & "  Wait-Process -Id $app.Id" & vbCrLf
ps = ps & "} finally {" & vbCrLf
ps = ps & "  if($server -and -not $server.HasExited){ & taskkill /PID $server.Id /T /F | Out-Null }" & vbCrLf
ps = ps & "  try { if($edgeProfile -and $edgeProfile.StartsWith([IO.Path]::GetTempPath())){ Remove-Item -Recurse -Force -Path $edgeProfile -EA SilentlyContinue } } catch {}" & vbCrLf
ps = ps & "}" & vbCrLf

Dim file
Set file = fso.CreateTextFile(psPath, True)
file.Write ps
file.Close

Dim cmd
cmd = "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & psPath & """ -Root """ & root & """"

' 0 = hidden, True = wait until PowerShell exits
shell.Run cmd, 0, True

' Cleanup temp .ps1
On Error Resume Next
fso.DeleteFile psPath, True
On Error GoTo 0
