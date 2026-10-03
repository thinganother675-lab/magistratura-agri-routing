$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskDocx = Join-Path $taskRoot 'manuscript/russian_resource_20261004.docx'
$taskPdf = Join-Path $taskRoot '.cache/article_qa_20261004/russian_resource_20261004_word.pdf'
$taskWord = $null
$taskDoc = $null
try {
    $taskWord = New-Object -ComObject Word.Application
    $taskWord.Visible = $false
    $taskWord.DisplayAlerts = 0
    $taskWord.AutomationSecurity = 3
    $taskDoc = $taskWord.Documents.Open($taskDocx, $false, $true, $false)
    $taskDoc.ExportAsFixedFormat($taskPdf, 17)
    Write-Output ('WordExport: ' + $taskPdf)
} finally {
    if ($null -ne $taskDoc) {
        $taskDoc.Close(0)
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskDoc)
    }
    if ($null -ne $taskWord) {
        $taskWord.Quit(0)
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskWord)
    }
}
