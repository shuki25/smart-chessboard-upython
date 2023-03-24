# This script compiles the project and creates a .mpy file in the project
# src directory and moves them to the project bytecode-compiled directory.

param(
  [string]$optimization = ""
)

foreach ($file in (Get-ChildItem -Path *.py)) {
    if ($optimization -eq "") {
        Write-Host "Byte compiling $($file.Name) ..."
        mpy-cross-v6 $file.Name
    }
    else {
        Write-Host "Byte compiling $($file.Name) with optimization $optimization ..."
        mpy-cross-v6 "-O$optimization" $file.Name
    }
}

Remove-Item boot.mpy, main.mpy -ErrorAction SilentlyContinue
Move-Item -Path "*.mpy" -Destination "../bytecode-compiled" -Force
