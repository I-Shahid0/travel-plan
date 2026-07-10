param(
    [Parameter(Mandatory)]
    [string]$Root,
    [string]$Release = "retrieval",
    [ValidateSet("local", "external")]
    [string]$Profile = "local",
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

function Parse-RedisUrl {
    param([string]$Url)

    $tls = $false
    $rest = $Url
    if ($Url.StartsWith("rediss://")) {
        $tls = $true
        $rest = $Url.Substring("rediss://".Length)
    } elseif ($Url.StartsWith("redis://")) {
        $rest = $Url.Substring("redis://".Length)
    } else {
        return $null
    }

    $slash = $rest.IndexOf("/")
    if ($slash -ge 0) {
        $rest = $rest.Substring(0, $slash)
    }

    $userpass = ""
    $hostport = $rest
    $at = $rest.IndexOf("@")
    if ($at -ge 0) {
        $userpass = $rest.Substring(0, $at)
        $hostport = $rest.Substring($at + 1)
    }

    $password = ""
    $colon = $userpass.IndexOf(":")
    if ($colon -ge 0) {
        $password = $userpass.Substring($colon + 1)
    }

    return [PSCustomObject]@{
        Address  = $hostport
        Password = $password
        Tls      = $tls
    }
}

$envPath = Join-Path $Root ".env"
if (-not (Test-Path $envPath)) {
    $envPath = Join-Path $Root ".env.example"
    Write-Warning "No .env found; using .env.example (copy to .env for local overrides)"
}

$vars = Read-DotEnv $envPath
$prefix = if ($env:HELM_FULLNAME_OVERRIDE) { $env:HELM_FULLNAME_OVERRIDE } else { $Release }

if ($Profile -eq "local") {
    $vars["DATABASE_URL"] = "postgresql+asyncpg://retrieval:retrieval@${prefix}-postgres:5432/retrieval"
    $vars["DATABASE_URL_SYNC"] = "postgresql://retrieval:retrieval@${prefix}-postgres:5432/retrieval"
    $vars["REDIS_URL"] = "redis://${prefix}-redis:6379/0"
    $vars["RERANKER_URL"] = "http://${prefix}-reranker:8001"
    $vars["QUERY_SERVICE_URL"] = "http://${prefix}-query:8000"
    $vars["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://${prefix}-otel-collector:4317"
    $vars["EMBEDDING_DEVICE"] = "cpu"
    $vars["RERANKER_DEVICE"] = "cpu"
}

$externalRedis = $null
if ($Profile -eq "external" -and $vars.ContainsKey("REDIS_URL") -and $vars["REDIS_URL"]) {
    $externalRedis = Parse-RedisUrl $vars["REDIS_URL"]
}

$secretKeys = @("DATABASE_URL", "DATABASE_URL_SYNC", "REDIS_URL", "GOOGLE_API_KEY", "FIRECRAWL_API_KEY")
$secrets = @{}
foreach ($secretKey in $secretKeys) {
    if ($vars.ContainsKey($secretKey) -and $vars[$secretKey]) {
        $secrets[$secretKey] = $vars[$secretKey]
        $vars.Remove($secretKey)
    }
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
if ($externalRedis) {
    $lines += "externalRedis:"
    $lines += "  address: `"$(Escape-Yaml $externalRedis.Address)`""
    $lines += "  password: `"$(Escape-Yaml $externalRedis.Password)`""
    $lines += "  tls: $($externalRedis.Tls.ToString().ToLower())"
}

$parent = Split-Path $OutFile -Parent
if ($parent -and -not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}
Set-Content -Path $OutFile -Value ($lines -join "`n") -Encoding UTF8
Write-Host "==> Wrote Helm env values (profile=$Profile) from $(Split-Path $envPath -Leaf) -> $OutFile"
