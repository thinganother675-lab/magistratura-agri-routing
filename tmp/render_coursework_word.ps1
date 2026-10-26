$ErrorActionPreference='Stop'
$taskWorkspace='C:\sarychev\Codex\magistratura'
$taskWord=$null
try {
    $taskWord=New-Object -ComObject Word.Application
    $taskWord.Visible=$false
    $taskWord.DisplayAlerts=0
    foreach ($variant in @(3,11)) {
        $taskInputDir=Join-Path $taskWorkspace "output/docx/mmm-ppr-variant-$variant"
        $taskOutputDir=Join-Path $taskWorkspace "tmp/docx/variant$variant/native"
        New-Item -ItemType Directory -Path $taskOutputDir -Force | Out-Null
        foreach ($taskFile in Get-ChildItem -LiteralPath $taskInputDir -Filter '*.docx') {
            $taskDocument=$null
            try {
                $taskDocument=$taskWord.Documents.Open($taskFile.FullName,$false,$true)
                $taskDocument.Fields.Update() | Out-Null
                $taskDocument.Repaginate()
                $taskPdf=Join-Path $taskOutputDir ($taskFile.BaseName+'.pdf')
                $taskDocument.ExportAsFixedFormat($taskPdf,17)
                Write-Output ($taskFile.Name+': '+$taskDocument.ComputeStatistics(2)+' pages -> '+$taskPdf)
            } finally {
                if ($null -ne $taskDocument) { $taskDocument.Close(0) }
            }
        }
    }
} finally {
    if ($null -ne $taskWord) { $taskWord.Quit() }
}
