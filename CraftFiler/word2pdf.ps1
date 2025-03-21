$p = $args[0]
if ($p -match "\.docx?$") {
    $w = New-Object -ComObject Word.Application
    $w.Visible = $false
    $d = $w.Documents.Open($p)
    $o = $p -replace "\.docx?$", ".pdf"

    $wdExportFormatPDF          = 17
    $wdExportOptimizeForPrint   = 0
    $wdExportAllDocument        = 0
    $wdExportDocumentWithMarkup = 7
    $OpenAfterExport            = $false
    $From                       = $null
    $To                         = $null

    $d.ExportAsFixedFormat($o, $wdExportFormatPDF, $OpenAfterExport, $wdExportOptimizeForPrint, $wdExportAllDocument, $From, $To, $wdExportDocumentWithMarkup)
    $d.Close($false)
    $w.Quit()

    Get-Variable | Where-Object {$_.Value -is [__ComObject]} | Clear-Variable
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    1 | ForEach-Object {$_} > $null

}
