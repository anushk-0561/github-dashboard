# GitHub Activity Dashboard Launcher
$username = Read-Host "Enter GitHub username"
Set-Location -Path "C:\GITHUB_DASHBOARD"
python main.py $username
Write-Host "`nPress Enter to exit..."
Read-Host