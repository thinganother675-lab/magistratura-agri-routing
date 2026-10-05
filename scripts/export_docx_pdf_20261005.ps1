# Enable Word hyphenation in the 20261005 editorial DOCX files and export PDF copies.
# Hyphenation is set through Word: a hand-written settings flag, or Save() on an
# editable open, made hidden automation hang. Each document is opened read-only in
# its own Word instance and re-saved with SaveAs2 to a temporary file that then
# replaces the original.
$root = Split-Path -Parent $PSScriptRoot
foreach ($name in @('russian_resource_20261005_claude', 'english_resource_20261005_claude')) {
    $docx = [System.IO.Path]::Combine($root, 'manuscript', "$name.docx")
    $pdf = [System.IO.Path]::Combine($root, 'manuscript', "${name}_word.pdf")
    $tmp = [System.IO.Path]::Combine($env:TEMP, "$name.hyph.docx")
    $w = New-Object -ComObject Word.Application
    $w.Visible = $false; $w.DisplayAlerts = 0; $w.AutomationSecurity = 3
    $d = $w.Documents.Open($docx, $false, $true, $false)
    $d.AutoHyphenation = $true
    $d.ExportAsFixedFormat($pdf, 17)
    $pages = $d.ComputeStatistics(2)
    $d.SaveAs2($tmp, 16)
    $d.Close([ref]0); $w.Quit([ref]0)
    Move-Item -LiteralPath $tmp -Destination $docx -Force
    Write-Output "WordExport: $pdf pages=$pages"
}
