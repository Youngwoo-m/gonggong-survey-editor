# 한글 문서를 PDF (와 원하면 HWP·HWPX) 로 뽑는다 — .hwp 와 .hwpx 를 함께 받는다.
#
# 스킬의 render_hwpx_to_pdf.ps1 은 여는 형식이 "HWPX" 로 박혀 있어 레거시 .hwp 를
# 열지 못하고, 파일을 여럿 넘길 때 -Paths 배열이 셸에 따라 한 덩이로 붙어 버린다.
# 그래서 파일 목록을 텍스트 파일(UTF-8, 한 줄에 하나)로 받는다.
#
#   -ListFile  <목록파일>     읽을 문서들
#   -OutDir    <폴더>         PDF 를 둘 곳 (없으면 원본 옆)
#   -AlsoHwp                  같은 이름의 .hwp 도 함께 뽑는다
param(
    [Parameter(Mandatory = $true)][string]$ListFile,
    [string]$OutDir = "",
    [switch]$AlsoHwp
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($env:windir)) { $env:windir = $env:SystemRoot }

$paths = @(Get-Content -LiteralPath $ListFile -Encoding UTF8 |
           Where-Object { $_.Trim().Length -gt 0 })
if ($paths.Count -eq 0) { Write-Output "빈 목록"; exit 0 }

$hwp = New-Object -ComObject HWPFrame.HwpObject
$ok = 0; $bad = 0
try {
    try { $null = $hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModuleExample") } catch {}

    foreach ($raw in $paths) {
        $p = [System.IO.Path]::GetFullPath($raw.Trim())
        $dir = if ($OutDir) { [System.IO.Path]::GetFullPath($OutDir) } else { [System.IO.Path]::GetDirectoryName($p) }
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
        $base = [System.IO.Path]::GetFileNameWithoutExtension($p)
        $ext = [System.IO.Path]::GetExtension($p).ToLower()
        $fmt = if ($ext -eq ".hwpx") { "HWPX" } else { "HWP" }
        try {
            if (-not $hwp.Open($p, $fmt, "forceopen:true")) { throw "열지 못함" }
            $pdf = Join-Path $dir ($base + ".pdf")
            if (-not $hwp.SaveAs($pdf, "PDF", "")) { throw "PDF 로 저장하지 못함" }
            $pages = $hwp.PageCount
            if ($AlsoHwp -and $ext -ne ".hwp") {
                $out = Join-Path $dir ($base + ".hwp")
                if (-not $hwp.SaveAs($out, "HWP", "")) { throw "HWP 로 저장하지 못함" }
            }
            Write-Output ("OK`t{0}`t{1}" -f $base, $pages)
            $ok++
        } catch {
            Write-Output ("FAIL`t{0}`t{1}" -f $base, $_.Exception.Message)
            $bad++
        }
        try { $hwp.Clear(1) } catch {}
    }
}
finally {
    try { $hwp.Quit() } catch {}
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($hwp)
}
Write-Output ("DONE`t{0}`t{1}" -f $ok, $bad)
if ($bad -gt 0) { exit 2 }
