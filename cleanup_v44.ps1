# Moves unneeded files into _to_delete\ (nothing is erased). Stop the server first (Ctrl+C in its window).
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$dest = Join-Path $root "_to_delete"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$items = @(
  "tests\test_app_smoke.py",              # old Streamlit test, would fail
  "checkpoints\balding_model.before_stamp.pt",   # backups made by stamp_artifact.py
  "checkpoints\scalp_model.before_stamp.pt",
  "logs\requests.jsonl",                  # test-run request log; the server makes a fresh one
  "cleanup_to_delete.ps1"                 # old cleanup script, already used
)
foreach ($i in $items) {
  if (Test-Path $i) {
    $target = Join-Path $dest ((Split-Path $i -Leaf))
    Move-Item -Force $i $target
    Write-Host "moved $i"
  } else { Write-Host "not found (skipped) $i" }
}
# Python cache folders are rebuilt automatically
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Where-Object { $_.FullName -notlike "*\_to_delete\*" } | ForEach-Object { Remove-Item -Recurse -Force $_.FullName; Write-Host "removed cache $($_.FullName)" }
Write-Host "Done. Check _to_delete\ and empty it yourself when sure."
