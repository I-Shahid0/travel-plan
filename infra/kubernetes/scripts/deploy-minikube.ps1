param(
    [ValidateSet("local", "external")]
    [string]$DeployProfile = "local"
)

$ErrorActionPreference = "Stop"

function Invoke-External {
    param(
        [Parameter(Mandatory)]
        [scriptblock]$Command,
        [switch]$AllowFailure
    )

    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Command
        if (-not $AllowFailure -and $LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Get-NativeOutput {
    param(
        [Parameter(Mandatory)]
        [scriptblock]$Command
    )

    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $lines = @(& $Command 2>&1 | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                $_.ToString()
            } else {
                [string]$_
            }
        })
        return ,$lines
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Get-MinikubeHealth {
    param([string]$Profile)

    $lines = Get-NativeOutput { minikube status -p $Profile }
    if (-not $lines -or ($lines | Where-Object { $_ -match "Profile .* not found" })) {
        return "missing"
    }

    $hostState = (($lines | Where-Object { $_ -match "^host:" }) -split ":", 2)[1].Trim()
    $apiState = (($lines | Where-Object { $_ -match "^apiserver:" }) -split ":", 2)[1].Trim()

    if ($hostState -eq "Running" -and $apiState -eq "Running") {
        return "healthy"
    }
    if ($hostState -eq "Running") {
        return "broken"
    }
    return "stopped"
}

function Wait-ClusterApi {
    param(
        [string]$Context,
        [int]$TimeoutSec = 180
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        Invoke-External -AllowFailure {
            kubectl cluster-info --context $Context *> $null
        } | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        Start-Sleep -Seconds 3
    }
    return $false
}

function Remove-MinikubeProfile {
    param([string]$Profile)

    Write-Host "==> Deleting minikube profile: $Profile"
    Invoke-External -AllowFailure {
        minikube stop -p $Profile
    } | Out-Null

    # minikube 1.38+ rejects `-p` when multiple profiles exist; fall back to --all.
    Invoke-External -AllowFailure {
        minikube delete -p $Profile --purge
    } | Out-Null

    if ((Get-MinikubeHealth $Profile) -ne "missing") {
        Write-Host "==> Single-profile delete unavailable; running minikube delete --all --purge"
        Invoke-External {
            minikube delete --all --purge
        } | Out-Null
    }
}

function Start-MinikubeProfile {
    param(
        [string]$Profile,
        [int]$Cpus,
        [int]$MemoryMb
    )

    # Free Docker resources if the default minikube profile is also running.
    Invoke-External -AllowFailure {
        minikube stop -p minikube
    } | Out-Null

    $k8sVersion = if ($env:MINIKUBE_K8S_VERSION) { $env:MINIKUBE_K8S_VERSION } else { "v1.31.4" }
    Write-Host "==> Starting minikube profile: $Profile (cpus=$Cpus memory=${MemoryMb}MB driver=docker k8s=$k8sVersion)"
    Invoke-External {
        minikube start -p $Profile `
            --driver=docker `
            --cpus=$Cpus `
            --memory=$MemoryMb `
            --kubernetes-version=$k8sVersion `
            --wait=all `
            --wait-timeout=10m
    } | Out-Null
}

function Ensure-Minikube {
    param([string]$Profile)

    Invoke-External {
        docker info *> $null
    } | Out-Null

    $cpus = if ($env:MINIKUBE_CPUS) { [int]$env:MINIKUBE_CPUS } else { 4 }
    $memory = if ($env:MINIKUBE_MEMORY) { [int]$env:MINIKUBE_MEMORY } else { 6144 }

    $health = Get-MinikubeHealth $Profile
    if ($health -eq "healthy") {
        Write-Host "==> Minikube profile already healthy: $Profile"
    } elseif ($health -eq "broken") {
        Write-Host "==> Minikube profile is broken (apiserver/kubelet stopped); recreating"
        Remove-MinikubeProfile $Profile
        Start-MinikubeProfile -Profile $Profile -Cpus $cpus -MemoryMb $memory
    } else {
        Start-MinikubeProfile -Profile $Profile -Cpus $cpus -MemoryMb $memory
    }

    Write-Host "==> Configuring kubectl context: $Profile"
    Invoke-External {
        kubectl config use-context $Profile
    } | Out-Null

    if (-not (Wait-ClusterApi -Context $Profile)) {
        Write-Host "==> Cluster API still unreachable; deleting profile and retrying with less memory"
        Remove-MinikubeProfile $Profile
        $retryMemory = [Math]::Max(4096, [int]($memory * 0.75))
        Start-MinikubeProfile -Profile $Profile -Cpus $cpus -MemoryMb $retryMemory
        Invoke-External {
            kubectl config use-context $Profile
        } | Out-Null
        if (-not (Wait-ClusterApi -Context $Profile)) {
            Write-Host ""
            Write-Host "Minikube failed to start. Try manually:"
            Write-Host "  minikube delete -p $Profile --purge"
            Write-Host "  minikube start -p $Profile --driver=docker --cpus=2 --memory=4096"
            Write-Host "  minikube logs -p $Profile"
            throw "Minikube profile $Profile is not reachable after retry"
        }
    }

    Write-Host "==> Enabling metrics-server addon (required for HPA)"
    Invoke-External -AllowFailure {
        minikube addons enable metrics-server -p $Profile
    } | Out-Null

    Write-Host "==> Cluster API ready"
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$Profile = if ($env:MINIKUBE_PROFILE) { $env:MINIKUBE_PROFILE } else { "retrieval" }
$Release = if ($env:RELEASE) { $env:RELEASE } else { "retrieval" }
$Chart = Join-Path $Root "infra\kubernetes\helm\retrieval-engine"

Ensure-Minikube -Profile $Profile

Write-Host "==> Installing KEDA operator (ScaledObject CRDs required by the chart)"
Invoke-External -AllowFailure {
    helm repo add kedacore https://kedacore.github.io/charts
} | Out-Null
Invoke-External -AllowFailure {
    helm repo update kedacore
} | Out-Null
Invoke-External {
    helm upgrade --install keda kedacore/keda --namespace keda --create-namespace --wait --timeout 5m
} | Out-Null

Write-Host "==> Building container images"
$imageTag = "dev-$(Get-Date -Format 'yyyyMMddHHmmss')"
foreach ($target in @("query", "reranker", "itinerary", "worker", "image-enrichment")) {
    $image = "retrieval-$target`:$imageTag"
    Invoke-External {
        docker build -f (Join-Path $Root "infra\docker\Dockerfile") --target $target -t $image $Root
    } | Out-Null
    Write-Host "    loading $image into minikube"
    Invoke-External {
        minikube image load $image -p $Profile
    } | Out-Null
}

Write-Host "==> Loading app env from .env (profile=$DeployProfile)"
$ValuesLocal = Join-Path $Chart "values.local.yaml"
$ValuesProfile = Join-Path $Chart "values-$DeployProfile.yaml"
& (Join-Path $PSScriptRoot "load-env.ps1") -Root $Root -Release $Release -Profile $DeployProfile -OutFile $ValuesLocal

Write-Host "==> Removing stale resources from pre-rename Helm revisions"
$staleKinds = @("deployment", "service", "statefulset", "horizontalpodautoscaler", "job")
foreach ($kind in $staleKinds) {
    $lines = @(Get-NativeOutput { kubectl get $kind -o name 2>$null })
    foreach ($name in $lines) {
        if ($name -notlike "*/retrieval-retrieval-engine-*") { continue }
        Write-Host "    deleting $name"
        Invoke-External -AllowFailure {
            kubectl delete $name --ignore-not-found
        } | Out-Null
    }
}

Write-Host "==> Deploying Helm chart (profile=$DeployProfile)"
$bootstrapIngest = if ($DeployProfile -eq "local") { "true" } else { "false" }
Invoke-External {
    helm upgrade --install $Release $Chart `
        -f $ValuesProfile `
        -f $ValuesLocal `
        --set image.tag=$imageTag `
        --set image.pullPolicy=Never `
        --set nodePort.enabled=true `
        --set bootstrap.sampleIngest.enabled=$bootstrapIngest `
        --wait --timeout 15m
} | Out-Null

Write-Host "==> Restarting workloads to pick up freshly loaded images"
Invoke-External -AllowFailure {
    kubectl rollout restart deployment -l "app.kubernetes.io/instance=$Release"
} | Out-Null
Invoke-External -AllowFailure {
    kubectl rollout status deployment -l "app.kubernetes.io/instance=$Release" --timeout=10m
} | Out-Null

Get-NativeOutput { kubectl get pods -l "app.kubernetes.io/instance=$Release" } | ForEach-Object { Write-Host $_ }

$querySvc = "$Release-query"
$itinerarySvc = "$Release-itinerary"
$jaegerSvc = "$Release-jaeger"
$grafanaSvc = "$Release-grafana"
$prometheusSvc = "$Release-prometheus"

Write-Host ""
Write-Host "Services (minikube NodePort URLs):"
Get-NativeOutput { minikube service list -p $Profile } | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "Quick access:"
Write-Host "  Query:     minikube service $querySvc -p $Profile --url"
Write-Host "  Itinerary: minikube service $itinerarySvc -p $Profile --url"
Write-Host "  Jaeger UI: minikube service $jaegerSvc -p $Profile --url"
Write-Host ""
Write-Host "Or port-forward (works without minikube tunnel):"
Write-Host "  kubectl port-forward svc/$querySvc 8000:8000"
Write-Host "  kubectl port-forward svc/$itinerarySvc 8002:8002"
Write-Host "  kubectl port-forward svc/$jaegerSvc 16686:16686"
Write-Host "  kubectl port-forward svc/$grafanaSvc 3000:3000"
Write-Host "  kubectl port-forward svc/$prometheusSvc 9090:9090"
