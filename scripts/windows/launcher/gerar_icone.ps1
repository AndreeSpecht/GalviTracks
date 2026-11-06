# Gera galvitracks.ico (16 a 256 px, PNG embutido) com a marca do painel:
# quadrado arredondado em degradê azul -> violeta com a seta de navegação branca.
Add-Type -AssemblyName System.Drawing
$ErrorActionPreference = 'Stop'
$destino = Join-Path $PSScriptRoot 'galvitracks.ico'
$tamanhos = 16, 24, 32, 48, 64, 128, 256
$pngs = @()

foreach ($t in $tamanhos) {
    $bmp = New-Object System.Drawing.Bitmap $t, $t, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'
    $g.Clear([System.Drawing.Color]::Transparent)

    $r = [single]($t * 0.22)
    $caminho = New-Object System.Drawing.Drawing2D.GraphicsPath
    $l = [single]($t - 1)
    $caminho.AddArc(0, 0, 2 * $r, 2 * $r, 180, 90)
    $caminho.AddArc($l - 2 * $r, 0, 2 * $r, 2 * $r, 270, 90)
    $caminho.AddArc($l - 2 * $r, $l - 2 * $r, 2 * $r, 2 * $r, 0, 90)
    $caminho.AddArc(0, $l - 2 * $r, 2 * $r, 2 * $r, 90, 90)
    $caminho.CloseFigure()
    $pincel = New-Object System.Drawing.Drawing2D.LinearGradientBrush (New-Object System.Drawing.PointF 0, 0), (New-Object System.Drawing.PointF $t, $t), ([System.Drawing.Color]::FromArgb(255, 37, 99, 235)), ([System.Drawing.Color]::FromArgb(255, 124, 58, 237))
    $g.FillPath($pincel, $caminho)

    # Seta de navegação (mesma forma do marcador do motoboy)
    $s = $t / 24.0
    $pts = @(
        (New-Object System.Drawing.PointF ([single](12 * $s)), ([single](4 * $s))),
        (New-Object System.Drawing.PointF ([single](18.5 * $s)), ([single](19.5 * $s))),
        (New-Object System.Drawing.PointF ([single](12 * $s)), ([single](16 * $s))),
        (New-Object System.Drawing.PointF ([single](5.5 * $s)), ([single](19.5 * $s)))
    )
    $g.FillPolygon([System.Drawing.Brushes]::White, [System.Drawing.PointF[]]$pts)
    $g.Dispose()

    $ms = New-Object System.IO.MemoryStream
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    $pngs += , @($t, $ms.ToArray())
}

# Arquivo ICO: cabeçalho + diretório + imagens PNG
$saida = New-Object System.IO.MemoryStream
$w = New-Object System.IO.BinaryWriter $saida
$w.Write([uint16]0); $w.Write([uint16]1); $w.Write([uint16]$pngs.Count)
$offset = 6 + 16 * $pngs.Count
foreach ($p in $pngs) {
    $t = $p[0]; $dados = $p[1]
    $lado = if ($t -ge 256) { 0 } else { $t }
    $w.Write([byte]$lado); $w.Write([byte]$lado); $w.Write([byte]0); $w.Write([byte]0)
    $w.Write([uint16]1); $w.Write([uint16]32)
    $w.Write([uint32]$dados.Length); $w.Write([uint32]$offset)
    $offset += $dados.Length
}
foreach ($p in $pngs) { $w.Write([byte[]]$p[1]) }
$w.Flush()
[System.IO.File]::WriteAllBytes($destino, $saida.ToArray())
Write-Output "Ícone gerado: $destino"
