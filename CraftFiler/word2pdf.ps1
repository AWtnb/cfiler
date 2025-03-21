$pp = @($args) | Where-Object {$_ -match "\.docx?$"}
if ($pp.count -gt 0) {
    $w = New-Object -ComObject Word.Application
    $w.Visible = $false

    $wdExportFormatPDF          = 17
    $wdExportOptimizeForPrint   = 0
    $wdExportAllDocument        = 0
    $wdExportDocumentWithMarkup = 7
    $OpenAfterExport            = $false
    $From                       = $null
    $To                         = $null

    $pp | ForEach-Object {
        $p = $_
        $d = $w.Documents.Open($p)
        $o = $p -replace "\.docx?$", ".pdf"
        $d.ExportAsFixedFormat($o, $wdExportFormatPDF, $OpenAfterExport, $wdExportOptimizeForPrint, $wdExportAllDocument, $From, $To, $wdExportDocumentWithMarkup)
        $d.Close($false)
        "converted to pdf: {0}" -f $p | Write-Host
    }

    $w.Quit()

    Get-Variable | Where-Object {$_.Value -is [__ComObject]} | Clear-Variable
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    1 | ForEach-Object {$_} > $null

}

