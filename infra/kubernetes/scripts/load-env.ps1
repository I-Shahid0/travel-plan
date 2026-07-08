param(
    [Parameter(Mandatory)]
    [string]$Root,
    [string]$Release = "retrieval",
    [Parameter(Mandatory)]
    [string]$OutFile
)

function Read-DotEnv {
    param([string]$Path)
    $result = @{}
    foreach ($line in Get-Content $Path) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { continue }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        $result[$key] = $val
    }
    return $result
}

$envPath = Join-Path $Root ".env"
if (-not (Test-Path $envPath)) {
    $envPath = Join-Path $Root ".env.example"
    Write-Warning "No .env found; using .env.example (copy to .env for local overrides)"
}

$vars = Read-DotEnv $envPath
$prefix = if ($env:HELM_FULLNAME_OVERRIDE) { $env:HELM_FULLNAME_OVERRIDE } else { $Release }

# Cluster DNS overrides — .env localhost URLs do not work inside pods.
$vars["DATABASE_URL"] = "postgresql+asyncpg://retrieval:retrieval@${prefix}-postgres:5432/retrieval"
$vars["DATABASE_URL_SYNC"] = "postgresql://retrieval:retrieval@${prefix}-postgres:5432/retrieval"
$vars["REDIS_URL"] = "redis://${prefix}-redis:6379/0"
$vars["RERANKER_URL"] = "http://${prefix}-reranker:8001"
$vars["QUERY_SERVICE_URL"] = "http://${prefix}-query:8000"
$vars["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://${prefix}-otel-collector:4317"
$vars["EMBEDDING_DEVICE"] = "cpu"
$vars["RERANKER_DEVICE"] = "cpu"

$secrets = @{}
if ($vars.ContainsKey("GOOGLE_API_KEY") -and $vars["GOOGLE_API_KEY"]) {
    $secrets["GOOGLE_API_KEY"] = $vars["GOOGLE_API_KEY"]
    $vars.Remove("GOOGLE_API_KEY")
}

function Escape-Yaml([string]$Value) {
    return $Value.Replace("\", "\\").Replace('"', '\"')
}

$lines = @("appEnv:")
foreach ($key in $vars.Keys) {
    $lines += "  ${key}: `"$(Escape-Yaml $vars[$key])`""
}
if ($secrets.Count -gt 0) {
    $lines += "appSecrets:"
    foreach ($key in $secrets.Keys) {
        $lines += "  ${key}: `"$(Escape-Yaml $secrets[$key])`""
    }
}

$parent = Split-Path $OutFile -Parent
if ($parent -and -not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}
Set-Content -Path $OutFile -Value ($lines -join "`n") -Encoding UTF8
Write-Host "==> Wrote Helm env values from $(Split-Path $envPath -Leaf) -> $OutFile"
