param(
    [Parameter(Mandatory = $true)]
    [string[]]$Paths,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($env:windir)) {
    $env:windir = $env:SystemRoot
}
$outputDir = [System.IO.Path]::GetFullPath($OutputDirectory)
[System.IO.Directory]::CreateDirectory($outputDir) | Out-Null

$hwp = New-Object -ComObject HWPFrame.HwpObject
try {
    try {
        $null = $hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModuleExample")
    } catch {}

    foreach ($path in $Paths) {
        $resolvedPath = [System.IO.Path]::GetFullPath($path)
        $opened = $hwp.Open($resolvedPath, "HWPX", "forceopen:true")
        if (-not $opened) {
            throw "Could not open HWPX: $resolvedPath"
        }

        $base = [System.IO.Path]::GetFileNameWithoutExtension($resolvedPath)
        $pdf = Join-Path $outputDir ($base + ".pdf")
        $saved = $hwp.SaveAs($pdf, "PDF", "")
        if (-not $saved) {
            throw "Could not save PDF: $pdf"
        }
        Write-Output ("RENDERED`t{0}`tPageCount={1}`tPDF={2}" -f $resolvedPath, $hwp.PageCount, $pdf)
        $hwp.Clear(1)
    }
}
finally {
    try { $hwp.Quit() } catch {}
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($hwp)
}
