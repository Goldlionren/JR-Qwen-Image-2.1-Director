param([Parameter(Mandatory=$true)][string]$ComfyRoot)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$custom = (Resolve-Path -LiteralPath (Join-Path $ComfyRoot 'custom_nodes')).Path
$target = Join-Path $custom 'ComfyUI-QwenImage21-Director'
if (!(Test-Path -LiteralPath (Join-Path $source 'web/dist/director.js'))) { throw 'Build first: npm ci; npm run build' }
if (Test-Path -LiteralPath $target) {
    $item = Get-Item -LiteralPath $target
    if ($item.LinkType -eq 'Junction' -and $item.Target -eq $source) { Write-Output "Already linked: $target"; exit 0 }
    throw "Target already exists; preserved without changes: $target"
}
New-Item -ItemType Junction -Path $target -Target $source | Out-Null
Write-Output "Linked $target -> $source. Restart ComfyUI to load the node."
