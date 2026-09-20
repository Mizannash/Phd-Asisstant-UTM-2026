$path = "D:\PhD_Assistant_UTM\src\scout.py"
$content = Get-Content $path -Raw
$content = $content -replace 'sys\.path\.append\(os\.path\.dirname\(__file__\)\)', 'sys.path.insert(0, os.path.dirname(__file__))'
Set-Content -Path $path -Value $content
Get-Content $path -TotalCount 12
