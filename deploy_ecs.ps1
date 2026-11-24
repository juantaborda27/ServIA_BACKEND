$ErrorActionPreference = "Continue"

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host " Despliegue Cloud ServIA en Amazon ECS (Fargate)        " -ForegroundColor Cyan -BackgroundColor DarkBlue
Write-Host " Capa 1: Presentacion (Fargate: Expo Web + nginx)      " -ForegroundColor White
Write-Host " Capa 2: Aplicacion   (Fargate: FastAPI + ALB /api/*)  " -ForegroundColor White
Write-Host " Capa 3: Datos        (Amazon RDS PostgreSQL Multi-AZ) " -ForegroundColor White
Write-Host "=======================================================" -ForegroundColor Cyan

# 1. Asegurar AWS CLI en el PATH si está instalado en Program Files
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    if (Test-Path "C:\Program Files\Amazon\AWSCLIV2\aws.exe") {
        $env:PATH = "C:\Program Files\Amazon\AWSCLIV2;$env:PATH"
    }
}

# 2. Cargar Credenciales de AWS Learner Lab automáticamente desde credentials.ps1
$CredFile = $null
foreach ($p in @(
    "$PSScriptRoot\credentials.ps1",
    "$PSScriptRoot\BACKEND\credentials.ps1",
    "$PSScriptRoot\..\credentials.ps1"
)) {
    if (Test-Path $p) { $CredFile = $p; break }
}

if ($CredFile) {
    . $CredFile
} else {
    Write-Host "[ERROR] No se encontro credentials.ps1." -ForegroundColor Red
    exit 1
}

$env:AWS_DEFAULT_REGION = "us-east-1"
$Region = "us-east-1"

# Detección inteligente de directorios
$BackendDir = $PSScriptRoot
if (-not (Test-Path "$BackendDir\app\main.py") -and (Test-Path "$BackendDir\BACKEND\app\main.py")) {
    $BackendDir = "$PSScriptRoot\BACKEND"
}

$FrontendDir = "$BackendDir\..\FRONTEND ESTE SI\Front-ServiceIA"
if (-not (Test-Path $FrontendDir)) {
    $FrontendDir = "$BackendDir\..\frontend"
}
if (-not (Test-Path $FrontendDir)) {
    $FrontendDir = "$PSScriptRoot\FRONTEND ESTE SI\Front-ServiceIA"
}

$AZ_A = "us-east-1a"
$AZ_B = "us-east-1b"

# Nombres de recursos ECS (distintos a los de deploy_s3.ps1 para que ambos puedan coexistir)
$ClusterName     = "servia-ecs-cluster"
$RepoBackend     = "servia-backend"
$RepoFrontend    = "servia-frontend"
$TdBackend       = "servia-backend"
$TdFrontend      = "servia-frontend"
$TdDbInit        = "servia-db-init"
$SvcBackend      = "servia-backend-service"
$SvcFrontend     = "servia-frontend-service"
$AlbName         = "alb-servia-ecs"
$TgBackName      = "tg-servia-ecs-back"
$TgFrontName     = "tg-servia-ecs-front"
$LogGroupBackend = "/ecs/servia-backend"
$LogGroupFront   = "/ecs/servia-frontend"
$LogGroupDbInit  = "/ecs/servia-db-init"
$SecretDbUrl     = "servia/database-url"
$SecretDbPass    = "servia/db-password"
$SecretJwt       = "servia/jwt-secret"
$SecretRedisUrl  = "servia/redis-url"
$DbPassword      = "PasswordSegura123"
$JwtSecret       = "_Av13cu#7-LfUNXa+xMUz6Y"
$RedisUrl        = if ($env:REDIS_URL) { $env:REDIS_URL.Trim() } else { "" }
$ImageTag        = "v" + (Get-Date -Format "yyyyMMdd-HHmmss")

# Carpeta temporal para JSON de la CLI y contexto Docker del frontend
$TmpDir = Join-Path $env:TEMP "servia-ecs-deploy"
if (Test-Path $TmpDir) { Remove-Item $TmpDir -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null

# Escribe un archivo UTF-8 sin BOM (la AWS CLI no acepta BOM en file://)
function Write-TmpFile {
    param($Name, $Content)
    $path = Join-Path $TmpDir $Name
    if ($Content -isnot [string]) { $Content = ConvertTo-Json -InputObject $Content -Depth 20 }
    [IO.File]::WriteAllText($path, $Content, (New-Object Text.UTF8Encoding $false))
    return $path
}

# =============================================================================
# FASE 0: VALIDACIONES PREVIAS (SESION AWS Y DOCKER)
# =============================================================================
$IdentityJson = aws sts get-caller-identity --output json 2>$null
$Ec2Test = aws ec2 describe-vpcs --max-items 1 2>&1

if ($LASTEXITCODE -ne 0 -or $Ec2Test -match "voc-cancel-cred" -or $Ec2Test -match "UnauthorizedOperation") {
    Write-Host ""
    Write-Host "=======================================================" -ForegroundColor Red
    Write-Host "[ERROR] Tu sesion de AWS Learner Lab ha expirado o esta detenida." -ForegroundColor Red
    Write-Host "=======================================================" -ForegroundColor Red
    Write-Host "Pasos para continuar:" -ForegroundColor Yellow
    Write-Host "1. Ve a tu plataforma de AWS Academy / Learner Lab." -ForegroundColor White
    Write-Host "2. Haz clic en 'Start Lab' y espera a que el circulo se ponga verde." -ForegroundColor White
    Write-Host "3. Haz clic en 'AWS Details' -> 'AWS CLI' y copia las credenciales nuevas." -ForegroundColor White
    Write-Host "4. Pegalas en el archivo credentials.ps1 y vuelve a ejecutar este script." -ForegroundColor White
    exit 1
}

docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Docker no esta en ejecucion. Inicia Docker Desktop y vuelve a ejecutar el script." -ForegroundColor Red
    Write-Host "        (Se necesita para construir las imagenes y subirlas a Amazon ECR)" -ForegroundColor DarkYellow
    exit 1
}

$AccountId = (aws sts get-caller-identity --query Account --output text).Trim()
$LabRoleArn = "arn:aws:iam::${AccountId}:role/LabRole"
$Registry = "$AccountId.dkr.ecr.$Region.amazonaws.com"
Write-Host "AWS Account ID: $AccountId" -ForegroundColor Cyan
Write-Host "Rol de tareas:  $LabRoleArn (unico rol permitido en Learner Lab)" -ForegroundColor Cyan

# =============================================================================
# FASE 1: RED MULTI-AZ (VPC, SUBREDES PUBLICAS/PRIVADAS Y NAT GATEWAY)
# =============================================================================
Write-Host ""
Write-Host "[Fase 1: Red Multi-AZ] Configurando VPC, subredes privadas para ECS y NAT Gateway..." -ForegroundColor Yellow

$VpcId = aws ec2 describe-vpcs --filters "Name=tag:Name,Values=servia_vpc" "Name=isDefault,Values=false" --query "Vpcs[0].VpcId" --output text 2>$null
if (-not $VpcId -or $VpcId -eq "None") {
    $VpcId = aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=servia_vpc}]" --query "Vpc.VpcId" --output text
    Write-Host "  -> VPC creada: $VpcId" -ForegroundColor Green
} else {
    Write-Host "  -> Reutilizando VPC existente: $VpcId" -ForegroundColor Green
}

aws ec2 modify-vpc-attribute --vpc-id $VpcId --enable-dns-support | Out-Null
aws ec2 modify-vpc-attribute --vpc-id $VpcId --enable-dns-hostnames | Out-Null

function Get-OrCreateSubnet {
    param($Name, $Cidr, $Az, $MapPublic = $false)
    $subId = aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VpcId" "Name=tag:Name,Values=$Name" --query "Subnets[0].SubnetId" --output text 2>$null
    if (-not $subId -or $subId -eq "None") {
        $subId = aws ec2 create-subnet --vpc-id $VpcId --cidr-block $Cidr --availability-zone $Az --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=$Name}]" --query "Subnet.SubnetId" --output text
        Write-Host "  -> Subred creada: $Name ($subId) en $Az" -ForegroundColor Green
    } else {
        Write-Host "  -> Subred existente: $Name ($subId)" -ForegroundColor DarkGray
    }
    if ($MapPublic) {
        aws ec2 modify-subnet-attribute --subnet-id $subId --map-public-ip-on-launch | Out-Null
    }
    return $subId
}

# Capa 1: Subredes Públicas (ALB y NAT Gateway)
$SubPubA = Get-OrCreateSubnet -Name "servia_sub_pub_a" -Cidr "10.0.1.0/24" -Az $AZ_A -MapPublic $true
$SubPubB = Get-OrCreateSubnet -Name "servia_sub_pub_b" -Cidr "10.0.2.0/24" -Az $AZ_B -MapPublic $true

# Capa 2: Subredes Privadas para tareas Fargate (sin IP pública, salida por NAT)
$SubEcsA = Get-OrCreateSubnet -Name "servia_sub_ecs_a" -Cidr "10.0.7.0/24" -Az $AZ_A
$SubEcsB = Get-OrCreateSubnet -Name "servia_sub_ecs_b" -Cidr "10.0.8.0/24" -Az $AZ_B

# Capa 3: Subredes Datos (RDS PostgreSQL Multi-AZ - estrictamente privadas)
$SubDbA  = Get-OrCreateSubnet -Name "servia_sub_db_a"  -Cidr "10.0.5.0/24" -Az $AZ_A
$SubDbB  = Get-OrCreateSubnet -Name "servia_sub_db_b"  -Cidr "10.0.6.0/24" -Az $AZ_B

# Internet Gateway
$IgwId = aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VpcId" --query "InternetGateways[0].InternetGatewayId" --output text 2>$null
if (-not $IgwId -or $IgwId -eq "None") {
    $IgwId = aws ec2 create-internet-gateway --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=servia_igw}]" --query "InternetGateway.InternetGatewayId" --output text
    aws ec2 attach-internet-gateway --vpc-id $VpcId --internet-gateway-id $IgwId | Out-Null
    Write-Host "  -> Internet Gateway creado y asociado: $IgwId" -ForegroundColor Green
} else {
    Write-Host "  -> Internet Gateway existente: $IgwId" -ForegroundColor DarkGray
}

# Tabla de Enrutamiento Pública (ALB y NAT Gateway)
$RtPub = aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VpcId" "Name=tag:Name,Values=servia_rt_pub" --query "RouteTables[0].RouteTableId" --output text 2>$null
if (-not $RtPub -or $RtPub -eq "None") {
    $RtPub = aws ec2 create-route-table --vpc-id $VpcId --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=servia_rt_pub}]" --query "RouteTable.RouteTableId" --output text
    aws ec2 create-route --route-table-id $RtPub --destination-cidr-block 0.0.0.0/0 --gateway-id $IgwId | Out-Null
}
aws ec2 associate-route-table --subnet-id $SubPubA --route-table-id $RtPub 2>$null | Out-Null
aws ec2 associate-route-table --subnet-id $SubPubB --route-table-id $RtPub 2>$null | Out-Null

# Tabla de Enrutamiento Privada para la Capa de Datos (sin salida a internet)
$RtDb = aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VpcId" "Name=tag:Name,Values=servia_rt_db" --query "RouteTables[0].RouteTableId" --output text 2>$null
if (-not $RtDb -or $RtDb -eq "None") {
    $RtDb = aws ec2 create-route-table --vpc-id $VpcId --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=servia_rt_db}]" --query "RouteTable.RouteTableId" --output text
}
aws ec2 associate-route-table --subnet-id $SubDbA --route-table-id $RtDb 2>$null | Out-Null
aws ec2 associate-route-table --subnet-id $SubDbB --route-table-id $RtDb 2>$null | Out-Null

# NAT Gateway: sin él las tareas Fargate en subredes privadas no pueden descargar
# imagenes de ECR ni leer Secrets Manager (CannotPullContainerError)
$NatId = aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$VpcId" "Name=tag:Name,Values=servia_nat_ecs" "Name=state,Values=pending,available" --query "NatGateways[0].NatGatewayId" --output text 2>$null
if (-not $NatId -or $NatId -eq "None") {
    Write-Host "  -> Creando NAT Gateway en $SubPubA (tarda 1-3 minutos)..." -ForegroundColor Cyan
    $EipAlloc = aws ec2 allocate-address --domain vpc --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=servia_nat_ecs_eip}]" --query "AllocationId" --output text
    $NatId = aws ec2 create-nat-gateway --subnet-id $SubPubA --allocation-id $EipAlloc --tag-specifications "ResourceType=natgateway,Tags=[{Key=Name,Value=servia_nat_ecs}]" --query "NatGateway.NatGatewayId" --output text
    Write-Host "  -> NAT Gateway creado: $NatId" -ForegroundColor Green
} else {
    Write-Host "  -> NAT Gateway existente: $NatId" -ForegroundColor DarkGray
}
aws ec2 wait nat-gateway-available --nat-gateway-ids $NatId 2>$null

# Tabla de Enrutamiento Privada para ECS (0.0.0.0/0 -> NAT)
$RtEcs = aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VpcId" "Name=tag:Name,Values=servia_rt_ecs_priv" --query "RouteTables[0].RouteTableId" --output text 2>$null
if (-not $RtEcs -or $RtEcs -eq "None") {
    $RtEcs = aws ec2 create-route-table --vpc-id $VpcId --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=servia_rt_ecs_priv}]" --query "RouteTable.RouteTableId" --output text
}
aws ec2 create-route --route-table-id $RtEcs --destination-cidr-block 0.0.0.0/0 --nat-gateway-id $NatId 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    aws ec2 replace-route --route-table-id $RtEcs --destination-cidr-block 0.0.0.0/0 --nat-gateway-id $NatId 2>$null | Out-Null
}
aws ec2 associate-route-table --subnet-id $SubEcsA --route-table-id $RtEcs 2>$null | Out-Null
aws ec2 associate-route-table --subnet-id $SubEcsB --route-table-id $RtEcs 2>$null | Out-Null
Write-Host "  -> Subredes ECS privadas enrutadas por NAT ($RtEcs)" -ForegroundColor Green

# =============================================================================
# FASE 2: GRUPOS DE SEGURIDAD ENCADENADOS (ALB -> SERVICIOS -> RDS)
# =============================================================================
Write-Host ""
Write-Host "[Fase 2: Security Groups] Creando cadena de confianza ALB -> Servicios -> RDS..." -ForegroundColor Yellow

function Get-OrCreateSG {
    param($Name, $Desc)
    $sgId = aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VpcId" "Name=group-name,Values=$Name" --query "SecurityGroups[0].GroupId" --output text 2>$null
    if (-not $sgId -or $sgId -eq "None") {
        $sgId = aws ec2 create-security-group --group-name $Name --description $Desc --vpc-id $VpcId --query "GroupId" --output text
        aws ec2 create-tags --resources $sgId --tags "Key=Name,Value=$Name" | Out-Null
        Write-Host "  -> Grupo de Seguridad creado: $Name ($sgId)" -ForegroundColor Green
    } else {
        Write-Host "  -> Grupo de Seguridad existente: $Name ($sgId)" -ForegroundColor DarkGray
    }
    return $sgId
}

$SgAlb   = Get-OrCreateSG -Name "sg_servia_ecs_alb"   -Desc "ECS ALB - HTTP 80 y API 8000 desde internet"
$SgBack  = Get-OrCreateSG -Name "sg_servia_ecs_back"  -Desc "ECS Backend - 8000 solo desde ALB"
$SgFront = Get-OrCreateSG -Name "sg_servia_ecs_front" -Desc "ECS Frontend - 80 solo desde ALB"
$SgRds   = Get-OrCreateSG -Name "sg_servia_rds"       -Desc "Capa 3: RDS PostgreSQL Database"

# ALB: 80 (app web) y 8000 (API directa / Swagger y respaldo del proxy nginx)
aws ec2 authorize-security-group-ingress --group-id $SgAlb --protocol tcp --port 80   --cidr 0.0.0.0/0 2>$null | Out-Null
aws ec2 authorize-security-group-ingress --group-id $SgAlb --protocol tcp --port 8000 --cidr 0.0.0.0/0 2>$null | Out-Null
# Contenedores: solo aceptan tráfico desde el ALB
aws ec2 authorize-security-group-ingress --group-id $SgBack  --protocol tcp --port 8000 --source-group $SgAlb 2>$null | Out-Null
aws ec2 authorize-security-group-ingress --group-id $SgFront --protocol tcp --port 80   --source-group $SgAlb 2>$null | Out-Null
# RDS: 5432 solo desde las tareas del backend (y la tarea de init, que usa el mismo SG)
aws ec2 authorize-security-group-ingress --group-id $SgRds --protocol tcp --port 5432 --source-group $SgBack 2>$null | Out-Null

# =============================================================================
# FASE 3: CAPA DE DATOS - AMAZON RDS POSTGRESQL MULTI-AZ
# =============================================================================
Write-Host ""
Write-Host "[Fase 3: Capa de Datos] Verificando Amazon RDS PostgreSQL Multi-AZ (servia-db-rds)..." -ForegroundColor Yellow

$SubnetGroupName = "servia-db-subnets"
aws rds describe-db-subnet-groups --db-subnet-group-name $SubnetGroupName 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    aws rds create-db-subnet-group `
      --db-subnet-group-name $SubnetGroupName `
      --db-subnet-group-description "Subredes privadas para ServIA RDS" `
      --subnet-ids $SubDbA $SubDbB 2>$null | Out-Null
    Write-Host "  -> DB Subnet Group creado: $SubnetGroupName" -ForegroundColor Green
}

$RdsCheck = aws rds describe-db-instances --db-instance-identifier servia-db-rds --query "DBInstances[0].DBInstanceStatus" --output text 2>$null
if ($RdsCheck -and $RdsCheck.Trim() -eq "deleting") {
    Write-Host "Esperando a que finalice la eliminacion previa de servia-db-rds..." -ForegroundColor DarkYellow
    while ($true) {
        $st = aws rds describe-db-instances --db-instance-identifier servia-db-rds --query "DBInstances[0].DBInstanceStatus" --output text 2>$null
        if (-not $st -or $st -eq "None" -or $st.Trim() -eq "") { break }
        Start-Sleep -Seconds 15
    }
    $RdsCheck = $null
}

if (-not $RdsCheck -or $RdsCheck -eq "None" -or $RdsCheck.Trim() -eq "") {
    Write-Host "Lanzando instancia RDS PostgreSQL Multi-AZ (db.t3.micro)..." -ForegroundColor Cyan
    aws rds create-db-instance `
      --db-instance-identifier servia-db-rds `
      --db-name servia_db `
      --db-instance-class db.t3.micro `
      --engine postgres `
      --engine-version 15 `
      --master-username postgres `
      --master-user-password $DbPassword `
      --allocated-storage 20 `
      --storage-type gp3 `
      --db-subnet-group-name $SubnetGroupName `
      --vpc-security-group-ids $SgRds `
      --no-publicly-accessible `
      --multi-az `
      --backup-retention-period 0 `
      --tags "Key=Name,Value=servia-db-rds" 2>$null | Out-Null
    Write-Host "  -> Solicitud de creacion de RDS enviada (se provisiona en segundo plano)." -ForegroundColor Green
} else {
    Write-Host "  -> Instancia RDS ya existe (Estado: $RdsCheck)" -ForegroundColor Green
}

# =============================================================================
# FASE 4: AMAZON ECR - CONSTRUIR Y PUBLICAR IMAGENES DOCKER
# =============================================================================
Write-Host ""
Write-Host "[Fase 4: Amazon ECR] Construyendo y publicando imagenes Docker (tag $ImageTag)..." -ForegroundColor Yellow

foreach ($repo in @($RepoBackend, $RepoFrontend)) {
    aws ecr describe-repositories --repository-names $repo 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        aws ecr create-repository --repository-name $repo --image-scanning-configuration scanOnPush=true 2>$null | Out-Null
        Write-Host "  -> Repositorio ECR creado: $repo" -ForegroundColor Green
    } else {
        Write-Host "  -> Repositorio ECR existente: $repo" -ForegroundColor DarkGray
    }
}

aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $Registry | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] No se pudo iniciar sesion de Docker en ECR ($Registry)." -ForegroundColor Red
    exit 1
}

# 4.1 Imagen del Backend (usa el Dockerfile existente del backend)
$ImageBackend = "$Registry/${RepoBackend}:$ImageTag"
Write-Host "Construyendo imagen del backend..." -ForegroundColor Cyan
docker build --platform linux/amd64 -t $ImageBackend -t "$Registry/${RepoBackend}:latest" "$BackendDir"
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Fallo docker build del backend." -ForegroundColor Red; exit 1 }
docker push $ImageBackend | Out-Null
docker push "$Registry/${RepoBackend}:latest" | Out-Null
Write-Host "  -> Backend publicado: $ImageBackend" -ForegroundColor Green

# 4.2 Imagen del Frontend: Expo Web compilado localmente + nginx con plantilla para ECS
# El frontend llama a "/api/..." (misma URL del ALB, sin CORS). El nginx.conf del repo apunta
# a "backend:8000" (docker-compose), que no existe en ECS; por eso se genera uno propio.
if (-not (Test-Path $FrontendDir)) {
    Write-Host "  [INFO] Directorio frontend no encontrado localmente. Clonando desde GitHub..." -ForegroundColor DarkYellow
    $FrontendDir = "$PSScriptRoot\Front-ServiceIA"
    git clone https://github.com/Dyelamo/Front-ServiceIA.git $FrontendDir 2>&1 | Out-Null
}
if (-not (Test-Path $FrontendDir)) {
    Write-Host "[ERROR] No se encontro el frontend." -ForegroundColor Red
    exit 1
}

$FrontCtx = Join-Path $TmpDir "frontend"
New-Item -ItemType Directory -Force -Path $FrontCtx | Out-Null

Push-Location $FrontendDir
Write-Host "Instalando dependencias de Node.js..." -ForegroundColor Cyan
npm install --no-audit --no-fund

# Respaldar los .env locales para que Expo use /api y restaurarlos después
$EnvBackups = @{}
foreach ($f in @(".env", ".env.local")) {
    if (Test-Path $f) { $EnvBackups[$f] = [IO.File]::ReadAllText((Resolve-Path $f)) }
    Set-Content -Path $f -Value "EXPO_PUBLIC_API_URL=/api" -Encoding ascii
}
$env:EXPO_PUBLIC_API_URL = "/api"

Write-Host "Compilando Frontend (EXPO_PUBLIC_API_URL=/api)..." -ForegroundColor Cyan
npx expo export -p web --clear --output-dir "$FrontCtx\dist"
$BuildOk = ($LASTEXITCODE -eq 0)

Remove-Item Env:EXPO_PUBLIC_API_URL -ErrorAction SilentlyContinue
foreach ($f in @(".env", ".env.local")) {
    if ($EnvBackups.ContainsKey($f)) {
        [IO.File]::WriteAllText((Join-Path (Get-Location) $f), $EnvBackups[$f], (New-Object Text.UTF8Encoding $false))
    } else {
        Remove-Item $f -ErrorAction SilentlyContinue
    }
}
Pop-Location

if (-not $BuildOk -or -not (Test-Path "$FrontCtx\dist\index.html")) {
    Write-Host "[ERROR] La compilacion del frontend no genero 'dist'. Revisa errores de npm/expo arriba." -ForegroundColor Red
    exit 1
}

# Plantilla nginx: la imagen oficial ejecuta envsubst sobre /etc/nginx/templates/*.template
# solo con variables definidas (BACKEND_HOST, BACKEND_PORT, NGINX_RESOLVER); $uri etc. se respetan.
$NginxTemplate = @'
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # Resolver de la VPC: el DNS del ALB cambia de IP, se re-resuelve en cada peticion
    resolver ${NGINX_RESOLVER} valid=30s ipv6=off;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Respaldo: si una peticion /api/ llega al frontend, se reenvia al listener API del ALB
    # quitando el prefijo /api (el backend FastAPI expone /auth, /publicaciones, /health...)
    location /api/ {
        set $servia_backend http://${BACKEND_HOST}:${BACKEND_PORT};
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass $servia_backend;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
'@
$FrontDockerfile = @'
FROM nginx:alpine
COPY dist /usr/share/nginx/html
COPY default.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 80
'@
Write-TmpFile -Name "frontend\default.conf.template" -Content ($NginxTemplate -replace "`r`n", "`n") | Out-Null
Write-TmpFile -Name "frontend\Dockerfile" -Content ($FrontDockerfile -replace "`r`n", "`n") | Out-Null

$ImageFrontend = "$Registry/${RepoFrontend}:$ImageTag"
Write-Host "Construyendo imagen del frontend (nginx)..." -ForegroundColor Cyan
docker build --platform linux/amd64 -t $ImageFrontend -t "$Registry/${RepoFrontend}:latest" "$FrontCtx"
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Fallo docker build del frontend." -ForegroundColor Red; exit 1 }
docker push $ImageFrontend | Out-Null
docker push "$Registry/${RepoFrontend}:latest" | Out-Null
Write-Host "  -> Frontend publicado: $ImageFrontend" -ForegroundColor Green

# =============================================================================
# FASE 5: CLOUDWATCH LOG GROUPS
# =============================================================================
Write-Host ""
Write-Host "[Fase 5: CloudWatch Logs] Creando grupos de logs (retencion 7 dias)..." -ForegroundColor Yellow
foreach ($lg in @($LogGroupBackend, $LogGroupFront, $LogGroupDbInit)) {
    aws logs create-log-group --log-group-name $lg 2>$null | Out-Null
    aws logs put-retention-policy --log-group-name $lg --retention-in-days 7 2>$null | Out-Null
    Write-Host "  -> Log group: $lg" -ForegroundColor Green
}

# =============================================================================
# FASE 6: TARGET GROUPS (TIPO IP) Y APPLICATION LOAD BALANCER
# =============================================================================
Write-Host ""
Write-Host "[Fase 6: Load Balancer] Creando Target Groups (IP) y ALB con enrutamiento por ruta..." -ForegroundColor Yellow

function Get-OrCreateTG {
    param($Name, $Port, $HealthPath)
    $arn = aws elbv2 describe-target-groups --names $Name --query "TargetGroups[0].TargetGroupArn" --output text 2>$null
    if (-not $arn -or $arn -eq "None") {
        # Fargate (awsvpc) exige target-type ip
        $arn = aws elbv2 create-target-group `
          --name $Name `
          --protocol HTTP `
          --port $Port `
          --vpc-id $VpcId `
          --target-type ip `
          --health-check-protocol HTTP `
          --health-check-path $HealthPath `
          --health-check-interval-seconds 30 `
          --health-check-timeout-seconds 5 `
          --healthy-threshold-count 2 `
          --unhealthy-threshold-count 3 `
          --matcher HttpCode=200 `
          --query "TargetGroups[0].TargetGroupArn" `
          --output text
        Write-Host "  -> Target Group creado: $Name" -ForegroundColor Green
    } else {
        Write-Host "  -> Target Group existente: $Name" -ForegroundColor DarkGray
    }
    aws elbv2 modify-target-group-attributes --target-group-arn $arn --attributes Key=deregistration_delay.timeout_seconds,Value=30 2>$null | Out-Null
    return $arn
}

$TgBack  = Get-OrCreateTG -Name $TgBackName  -Port 8000 -HealthPath "/health"
$TgFront = Get-OrCreateTG -Name $TgFrontName -Port 80   -HealthPath "/"

$AlbArn = aws elbv2 describe-load-balancers --names $AlbName --query "LoadBalancers[0].LoadBalancerArn" --output text 2>$null
if (-not $AlbArn -or $AlbArn -eq "None") {
    $AlbArn = aws elbv2 create-load-balancer `
      --name $AlbName `
      --subnets $SubPubA $SubPubB `
      --security-groups $SgAlb `
      --scheme internet-facing `
      --ip-address-type ipv4 `
      --query "LoadBalancers[0].LoadBalancerArn" `
      --output text
    Write-Host "  -> ALB creado: $AlbName (esperando estado Active...)" -ForegroundColor Green
} else {
    Write-Host "  -> ALB existente: $AlbName" -ForegroundColor DarkGray
}
aws elbv2 wait load-balancer-available --load-balancer-arns $AlbArn 2>$null
$AlbDns = (aws elbv2 describe-load-balancers --load-balancer-arns $AlbArn --query "LoadBalancers[0].DNSName" --output text).Trim()
Write-Host "ALB DNS: $AlbDns" -ForegroundColor Cyan

# Listener :80 -> por defecto al frontend
$Listener80 = aws elbv2 describe-listeners --load-balancer-arn $AlbArn --query "Listeners[?Port==``80``].ListenerArn | [0]" --output text 2>$null
if (-not $Listener80 -or $Listener80 -eq "None") {
    $Listener80 = aws elbv2 create-listener `
      --load-balancer-arn $AlbArn `
      --protocol HTTP --port 80 `
      --default-actions Type=forward,TargetGroupArn=$TgFront `
      --query "Listeners[0].ListenerArn" --output text
    Write-Host "  -> Listener HTTP:80 (default -> frontend)" -ForegroundColor Green
}

# Listener :8000 -> backend directo (Swagger /docs y destino del proxy nginx)
$Listener8000 = aws elbv2 describe-listeners --load-balancer-arn $AlbArn --query "Listeners[?Port==``8000``].ListenerArn | [0]" --output text 2>$null
if (-not $Listener8000 -or $Listener8000 -eq "None") {
    $Listener8000 = aws elbv2 create-listener `
      --load-balancer-arn $AlbArn `
      --protocol HTTP --port 8000 `
      --default-actions Type=forward,TargetGroupArn=$TgBack `
      --query "Listeners[0].ListenerArn" --output text
    Write-Host "  -> Listener HTTP:8000 (default -> backend)" -ForegroundColor Green
}

# Regla /api/* (prioridad 10) -> backend, reescribiendo la URL para quitar el prefijo /api
$ApiRule = aws elbv2 describe-rules --listener-arn $Listener80 --query "Rules[?Priority=='10'].RuleArn | [0]" --output text 2>$null
$ApiRuleOk = ($ApiRule -and $ApiRule -ne "None")
if (-not $ApiRuleOk) {
    $condFile = Write-TmpFile -Name "rule_conditions.json" -Content '[{"Field":"path-pattern","PathPatternConfig":{"Values":["/api/*"]}}]'
    $actFile  = Write-TmpFile -Name "rule_actions.json"    -Content ('[{"Type":"forward","TargetGroupArn":"' + $TgBack + '"}]')
    $trFile   = Write-TmpFile -Name "rule_transforms.json" -Content '[{"Type":"url-rewrite","UrlRewriteConfig":{"Rewrites":[{"Regex":"^/api/(.*)$","Replace":"/$1"}]}}]'
    $ruleOut = aws elbv2 create-rule `
      --listener-arn $Listener80 `
      --priority 10 `
      --conditions "file://$condFile" `
      --actions "file://$actFile" `
      --transforms "file://$trFile" 2>&1
    if ($LASTEXITCODE -eq 0) {
        $ApiRuleOk = $true
        Write-Host "  -> Regla /api/* -> backend (url-rewrite ^/api/(.*)$ -> /`$1) creada" -ForegroundColor Green
    } else {
        Write-Host "  -> [AVISO] No se pudo crear la regla /api/* con url-rewrite: $ruleOut" -ForegroundColor DarkYellow
        Write-Host "     Las llamadas /api/* las atendera el proxy nginx del frontend via ALB:8000." -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  -> Regla /api/* existente" -ForegroundColor DarkGray
}

# =============================================================================
# FASE 7: CLUSTER ECS (FARGATE)
# =============================================================================
Write-Host ""
Write-Host "[Fase 7: Cluster ECS] Configurando cluster $ClusterName..." -ForegroundColor Yellow
$ClusterStatus = aws ecs describe-clusters --clusters $ClusterName --query "clusters[0].status" --output text 2>$null
if ($ClusterStatus -ne "ACTIVE") {
    aws ecs create-cluster --cluster-name $ClusterName --capacity-providers FARGATE --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 2>$null | Out-Null
    Write-Host "  -> Cluster ECS creado: $ClusterName" -ForegroundColor Green
} else {
    Write-Host "  -> Cluster ECS existente: $ClusterName" -ForegroundColor DarkGray
}

# =============================================================================
# FASE 8: ESPERAR RDS Y GUARDAR SECRETOS EN SECRETS MANAGER
# =============================================================================
Write-Host ""
Write-Host "[Fase 8: Secrets Manager] Esperando RDS disponible para generar los secretos..." -ForegroundColor Yellow
while ($true) {
    $st = aws rds describe-db-instances --db-instance-identifier servia-db-rds --query "DBInstances[0].DBInstanceStatus" --output text 2>$null
    if ($st -and $st.Trim() -eq "available") { break }
    Write-Host "  -> RDS en estado '$st' (Multi-AZ tarda 10-20 min), esperando 30s..." -ForegroundColor DarkYellow
    Start-Sleep -Seconds 30
}
$RdsEndpoint = (aws rds describe-db-instances --db-instance-identifier servia-db-rds --query "DBInstances[0].Endpoint.Address" --output text).Trim()
Write-Host "  -> RDS disponible: $RdsEndpoint" -ForegroundColor Green

# Secretos en texto plano (no JSON): ECS inyecta el valor tal cual como variable de entorno
function Set-PlainSecret {
    param($Name, $Value, $Desc)
    $valFile = Write-TmpFile -Name "secret_value.txt" -Content $Value
    $arn = aws secretsmanager describe-secret --secret-id $Name --query "ARN" --output text 2>$null
    if ($LASTEXITCODE -eq 0 -and $arn -and $arn -ne "None") {
        $deleted = aws secretsmanager describe-secret --secret-id $Name --query "DeletedDate" --output text 2>$null
        if ($deleted -and $deleted -ne "None") {
            aws secretsmanager restore-secret --secret-id $Name 2>$null | Out-Null
        }
        aws secretsmanager put-secret-value --secret-id $Name --secret-string "file://$valFile" 2>$null | Out-Null
        Write-Host "  -> Secreto actualizado: $Name" -ForegroundColor DarkGray
    } else {
        $arn = aws secretsmanager create-secret --name $Name --description $Desc --secret-string "file://$valFile" --query "ARN" --output text
        Write-Host "  -> Secreto creado: $Name" -ForegroundColor Green
    }
    Remove-Item $valFile -Force -ErrorAction SilentlyContinue
    return $arn.Trim()
}

$SecretDbUrlArn  = Set-PlainSecret -Name $SecretDbUrl  -Value "postgresql+asyncpg://postgres:${DbPassword}@${RdsEndpoint}:5432/servia_db" -Desc "ServIA DATABASE_URL (asyncpg)"
$SecretDbPassArn = Set-PlainSecret -Name $SecretDbPass -Value $DbPassword -Desc "ServIA contrasena maestra de RDS"
$SecretJwtArn    = Set-PlainSecret -Name $SecretJwt    -Value $JwtSecret  -Desc "ServIA JWT secret key"
$SecretRedisUrlArn = $null
if ($RedisUrl) {
    $SecretRedisUrlArn = Set-PlainSecret -Name $SecretRedisUrl -Value $RedisUrl -Desc "ServIA Redis URL para chat distribuido"
} else {
    Write-Host "  -> REDIS_URL no fue suministrada; el backend usara WebSockets locales." -ForegroundColor DarkYellow
    Write-Host "     Antes de desplegar en multiples tareas: `$env:REDIS_URL='rediss://endpoint:6379/0'" -ForegroundColor DarkYellow
}

# =============================================================================
# FASE 9: TASK DEFINITIONS (BACKEND, FRONTEND E INICIALIZACION DE BD)
# =============================================================================
Write-Host ""
Write-Host "[Fase 9: Task Definitions] Registrando task definitions de Fargate (rol LabRole)..." -ForegroundColor Yellow

function New-LogConfig {
    param($Group, $Prefix)
    return [ordered]@{
        logDriver = "awslogs"
        options   = [ordered]@{
            "awslogs-group"         = $Group
            "awslogs-region"        = $Region
            "awslogs-stream-prefix" = $Prefix
        }
    }
}

function Register-TaskDef {
    param($FileName, $Def)
    $f = Write-TmpFile -Name $FileName -Content $Def
    $arn = aws ecs register-task-definition --cli-input-json "file://$f" --query "taskDefinition.taskDefinitionArn" --output text
    if ($LASTEXITCODE -ne 0 -or -not $arn) {
        Write-Host "[ERROR] No se pudo registrar $FileName" -ForegroundColor Red
        exit 1
    }
    Write-Host "  -> Registrada: $arn" -ForegroundColor Green
    return $arn.Trim()
}

# 9.1 Backend FastAPI (0.5 vCPU / 1 GB)
$BackendSecrets = @(
    [ordered]@{ name = "DATABASE_URL";   valueFrom = $SecretDbUrlArn },
    [ordered]@{ name = "JWT_SECRET_KEY"; valueFrom = $SecretJwtArn }
)
if ($SecretRedisUrlArn) {
    $BackendSecrets += [ordered]@{ name = "REDIS_URL"; valueFrom = $SecretRedisUrlArn }
}

$TdBackendArn = Register-TaskDef -FileName "td_backend.json" -Def ([ordered]@{
    family                  = $TdBackend
    networkMode             = "awsvpc"
    requiresCompatibilities = @("FARGATE")
    cpu                     = "512"
    memory                  = "1024"
    runtimePlatform         = [ordered]@{ cpuArchitecture = "X86_64"; operatingSystemFamily = "LINUX" }
    executionRoleArn        = $LabRoleArn
    taskRoleArn             = $LabRoleArn
    containerDefinitions    = @(
        [ordered]@{
            name             = "servia-backend"
            image            = $ImageBackend
            essential        = $true
            portMappings     = @( [ordered]@{ containerPort = 8000; protocol = "tcp"; appProtocol = "http" } )
            environment      = @(
                [ordered]@{ name = "PYTHONUNBUFFERED";  value = "1" },
                [ordered]@{ name = "REDIS_REQUIRED";    value = $(if ($SecretRedisUrlArn) { "true" } else { "false" }) },
                [ordered]@{ name = "REDIS_CHAT_CHANNEL"; value = "servia:chat:events" }
            )
            secrets          = $BackendSecrets
            logConfiguration = (New-LogConfig -Group $LogGroupBackend -Prefix "backend")
        }
    )
})

# 9.2 Frontend nginx (0.25 vCPU / 0.5 GB)
$TdFrontendArn = Register-TaskDef -FileName "td_frontend.json" -Def ([ordered]@{
    family                  = $TdFrontend
    networkMode             = "awsvpc"
    requiresCompatibilities = @("FARGATE")
    cpu                     = "256"
    memory                  = "512"
    runtimePlatform         = [ordered]@{ cpuArchitecture = "X86_64"; operatingSystemFamily = "LINUX" }
    executionRoleArn        = $LabRoleArn
    taskRoleArn             = $LabRoleArn
    containerDefinitions    = @(
        [ordered]@{
            name             = "servia-frontend"
            image            = $ImageFrontend
            essential        = $true
            portMappings     = @( [ordered]@{ containerPort = 80; protocol = "tcp"; appProtocol = "http" } )
            environment      = @(
                [ordered]@{ name = "BACKEND_HOST";   value = $AlbDns },
                [ordered]@{ name = "BACKEND_PORT";   value = "8000" },
                [ordered]@{ name = "NGINX_RESOLVER"; value = "169.254.169.253" }
            )
            logConfiguration = (New-LogConfig -Group $LogGroupFront -Prefix "frontend")
        }
    )
})

# 9.3 Tarea única de inicialización de BD: psql ejecuta init.sql (idempotente) contra RDS
$InitSqlB64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$BackendDir\init.sql"))
$InitCmd = 'set -e; echo "$INIT_SQL_B64" | base64 -d > /tmp/init.sql; ' +
           'until pg_isready -h "$DB_HOST" -p 5432 -U postgres; do echo "Esperando RDS..."; sleep 5; done; ' +
           'psql -h "$DB_HOST" -U postgres -d servia_db -f /tmp/init.sql; echo OK_DB_INIT_COMPLETE'

$TdDbInitArn = Register-TaskDef -FileName "td_dbinit.json" -Def ([ordered]@{
    family                  = $TdDbInit
    networkMode             = "awsvpc"
    requiresCompatibilities = @("FARGATE")
    cpu                     = "256"
    memory                  = "512"
    runtimePlatform         = [ordered]@{ cpuArchitecture = "X86_64"; operatingSystemFamily = "LINUX" }
    executionRoleArn        = $LabRoleArn
    taskRoleArn             = $LabRoleArn
    containerDefinitions    = @(
        [ordered]@{
            name             = "servia-db-init"
            image            = "public.ecr.aws/docker/library/postgres:16-alpine"
            essential        = $true
            entryPoint       = @("sh", "-c")
            command          = @($InitCmd)
            environment      = @(
                [ordered]@{ name = "DB_HOST";      value = $RdsEndpoint },
                [ordered]@{ name = "INIT_SQL_B64"; value = $InitSqlB64 }
            )
            secrets          = @( [ordered]@{ name = "PGPASSWORD"; valueFrom = $SecretDbPassArn } )
            logConfiguration = (New-LogConfig -Group $LogGroupDbInit -Prefix "dbinit")
        }
    )
})

# =============================================================================
# FASE 10: INICIALIZAR ESQUEMA Y SEMILLAS EN RDS (TAREA FARGATE ONE-OFF)
# =============================================================================
Write-Host ""
Write-Host "[Fase 10: Init BD] Ejecutando init.sql en RDS con una tarea Fargate one-off..." -ForegroundColor Yellow

$NetCfg = "awsvpcConfiguration={subnets=[$SubEcsA,$SubEcsB],securityGroups=[$SgBack],assignPublicIp=DISABLED}"
$InitTaskArn = aws ecs run-task `
  --cluster $ClusterName `
  --launch-type FARGATE `
  --task-definition $TdDbInitArn `
  --network-configuration $NetCfg `
  --query "tasks[0].taskArn" --output text 2>$null

if ($InitTaskArn -and $InitTaskArn -ne "None") {
    Write-Host "  -> Tarea lanzada, esperando que finalice..." -ForegroundColor Cyan
    aws ecs wait tasks-stopped --cluster $ClusterName --tasks $InitTaskArn 2>$null
    $InitExit = aws ecs describe-tasks --cluster $ClusterName --tasks $InitTaskArn --query "tasks[0].containers[0].exitCode" --output text 2>$null
    if ($InitExit -eq "0") {
        Write-Host "  -> [OK] init.sql aplicado correctamente en servia_db." -ForegroundColor Green
    } else {
        $InitReason = aws ecs describe-tasks --cluster $ClusterName --tasks $InitTaskArn --query "tasks[0].stoppedReason" --output text 2>$null
        Write-Host "  -> [AVISO] La tarea de init termino con codigo '$InitExit' ($InitReason)." -ForegroundColor DarkYellow
        Write-Host "     Revisa CloudWatch Logs: $LogGroupDbInit" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  -> [AVISO] No se pudo lanzar la tarea de inicializacion de BD." -ForegroundColor DarkYellow
}

# =============================================================================
# FASE 11: SERVICIOS ECS (BACKEND Y FRONTEND) CON CIRCUIT BREAKER
# =============================================================================
Write-Host ""
Write-Host "[Fase 11: Servicios ECS] Creando/actualizando servicios (2 tareas Multi-AZ cada uno)..." -ForegroundColor Yellow

function Deploy-EcsService {
    param($ServiceName, $TaskDefArn, $SgId, $TgArn, $ContainerName, $ContainerPort, $GraceSeconds)
    $status = aws ecs describe-services --cluster $ClusterName --services $ServiceName --query "services[0].status" --output text 2>$null
    if ($status -eq "ACTIVE") {
        aws ecs update-service `
          --cluster $ClusterName `
          --service $ServiceName `
          --task-definition $TaskDefArn `
          --desired-count 2 `
          --health-check-grace-period-seconds $GraceSeconds `
          --force-new-deployment 2>$null | Out-Null
        Write-Host "  -> Servicio actualizado: $ServiceName -> $TaskDefArn" -ForegroundColor Green
    } else {
        $svcFile = Write-TmpFile -Name "svc_$ServiceName.json" -Content ([ordered]@{
            cluster                       = $ClusterName
            serviceName                   = $ServiceName
            taskDefinition                = $TaskDefArn
            desiredCount                  = 2
            launchType                    = "FARGATE"
            platformVersion               = "LATEST"
            healthCheckGracePeriodSeconds = $GraceSeconds
            networkConfiguration          = [ordered]@{
                awsvpcConfiguration = [ordered]@{
                    subnets        = @($SubEcsA, $SubEcsB)
                    securityGroups = @($SgId)
                    assignPublicIp = "DISABLED"
                }
            }
            loadBalancers                 = @(
                [ordered]@{ targetGroupArn = $TgArn; containerName = $ContainerName; containerPort = $ContainerPort }
            )
            deploymentConfiguration       = [ordered]@{
                deploymentCircuitBreaker = [ordered]@{ enable = $true; rollback = $true }
                maximumPercent           = 200
                minimumHealthyPercent    = 100
            }
        })
        aws ecs create-service --cli-input-json "file://$svcFile" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  -> Servicio creado: $ServiceName" -ForegroundColor Green
        } else {
            Write-Host "  -> [ERROR] No se pudo crear el servicio $ServiceName" -ForegroundColor Red
        }
    }
}

Deploy-EcsService -ServiceName $SvcBackend  -TaskDefArn $TdBackendArn  -SgId $SgBack  -TgArn $TgBack  -ContainerName "servia-backend"  -ContainerPort 8000 -GraceSeconds 120
Deploy-EcsService -ServiceName $SvcFrontend -TaskDefArn $TdFrontendArn -SgId $SgFront -TgArn $TgFront -ContainerName "servia-frontend" -ContainerPort 80   -GraceSeconds 60

# =============================================================================
# FASE 12: SERVICE AUTO SCALING (TARGET TRACKING CPU 70%, MIN 2 / MAX 4)
# =============================================================================
Write-Host ""
Write-Host "[Fase 12: Auto Scaling] Configurando escalado automatico por CPU (70%)..." -ForegroundColor Yellow
$ScalingCfg = Write-TmpFile -Name "scaling_policy.json" -Content ([ordered]@{
    TargetValue                   = 70.0
    PredefinedMetricSpecification = [ordered]@{ PredefinedMetricType = "ECSServiceAverageCPUUtilization" }
    ScaleOutCooldown              = 60
    ScaleInCooldown               = 300
})

foreach ($svc in @($SvcBackend, $SvcFrontend)) {
    $resId = "service/$ClusterName/$svc"
    aws application-autoscaling register-scalable-target `
      --service-namespace ecs `
      --resource-id $resId `
      --scalable-dimension ecs:service:DesiredCount `
      --min-capacity 2 --max-capacity 4 2>$null | Out-Null
    $polOut = aws application-autoscaling put-scaling-policy `
      --service-namespace ecs `
      --resource-id $resId `
      --scalable-dimension ecs:service:DesiredCount `
      --policy-name "$svc-cpu70" `
      --policy-type TargetTrackingScaling `
      --target-tracking-scaling-policy-configuration "file://$ScalingCfg" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  -> [OK] $svc : min=2, max=4, CPU objetivo 70%" -ForegroundColor Green
    } else {
        Write-Host "  -> [WARN] No se pudo aplicar la politica a ${svc}: $polOut" -ForegroundColor DarkYellow
    }
}

# =============================================================================
# FASE 13: MONITOREO - ALARMAS CLOUDWATCH (ECS + ALB + RDS)
# =============================================================================
Write-Host ""
Write-Host "[Fase 13: CloudWatch] Configurando alarmas de monitoreo..." -ForegroundColor Yellow

$SnsTopicName = "servia-alertas-ecs"
$SnsTopicArn  = (aws sns create-topic --name $SnsTopicName --query "TopicArn" --output text 2>$null)
$AlbDim       = ($AlbArn -replace "^arn:aws:elasticloadbalancing:[^:]+:[^:]+:loadbalancer/", "")
$TgBackDim    = ($TgBack -replace "^arn:aws:elasticloadbalancing:[^:]+:[^:]+:", "")
$TgFrontDim   = ($TgFront -replace "^arn:aws:elasticloadbalancing:[^:]+:[^:]+:", "")

function Set-Alarm {
    param($Name, $Desc, $Namespace, $Metric, [string[]]$Dims, $Stat, $Threshold, $Op, $Period, $Evals)
    aws cloudwatch put-metric-alarm `
      --alarm-name $Name `
      --alarm-description $Desc `
      --namespace $Namespace `
      --metric-name $Metric `
      --dimensions $Dims `
      --statistic $Stat `
      --threshold $Threshold `
      --comparison-operator $Op `
      --period $Period `
      --evaluation-periods $Evals `
      --treat-missing-data notBreaching `
      --alarm-actions $SnsTopicArn `
      --ok-actions $SnsTopicArn 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host "  -> [OK] $Name" -ForegroundColor Green }
    else { Write-Host "  -> [WARN] No se pudo crear la alarma $Name" -ForegroundColor DarkYellow }
}

Set-Alarm -Name "servia-ecs-backend-cpu-alta" -Desc "CPU del servicio backend ECS > 80%" -Namespace "AWS/ECS" -Metric "CPUUtilization" `
  -Dims @("Name=ClusterName,Value=$ClusterName", "Name=ServiceName,Value=$SvcBackend") -Stat "Average" -Threshold 80 -Op "GreaterThanThreshold" -Period 60 -Evals 3
Set-Alarm -Name "servia-ecs-backend-memoria-alta" -Desc "Memoria del servicio backend ECS > 85%" -Namespace "AWS/ECS" -Metric "MemoryUtilization" `
  -Dims @("Name=ClusterName,Value=$ClusterName", "Name=ServiceName,Value=$SvcBackend") -Stat "Average" -Threshold 85 -Op "GreaterThanThreshold" -Period 60 -Evals 3
Set-Alarm -Name "servia-ecs-alb-errores-5xx" -Desc "Errores 5XX del ALB ECS > 10 por minuto" -Namespace "AWS/ApplicationELB" -Metric "HTTPCode_ELB_5XX_Count" `
  -Dims @("Name=LoadBalancer,Value=$AlbDim") -Stat "Sum" -Threshold 10 -Op "GreaterThanThreshold" -Period 60 -Evals 2
Set-Alarm -Name "servia-ecs-backend-hosts-bajos" -Desc "Menos de 2 tareas backend saludables" -Namespace "AWS/ApplicationELB" -Metric "HealthyHostCount" `
  -Dims @("Name=LoadBalancer,Value=$AlbDim", "Name=TargetGroup,Value=$TgBackDim") -Stat "Minimum" -Threshold 2 -Op "LessThanThreshold" -Period 60 -Evals 2
Set-Alarm -Name "servia-ecs-frontend-hosts-bajos" -Desc "Menos de 2 tareas frontend saludables" -Namespace "AWS/ApplicationELB" -Metric "HealthyHostCount" `
  -Dims @("Name=LoadBalancer,Value=$AlbDim", "Name=TargetGroup,Value=$TgFrontDim") -Stat "Minimum" -Threshold 2 -Op "LessThanThreshold" -Period 60 -Evals 2
Set-Alarm -Name "servia-ecs-rds-cpu-alta" -Desc "CPU de RDS PostgreSQL > 75%" -Namespace "AWS/RDS" -Metric "CPUUtilization" `
  -Dims @("Name=DBInstanceIdentifier,Value=servia-db-rds") -Stat "Average" -Threshold 75 -Op "GreaterThanThreshold" -Period 60 -Evals 3

Write-Host "  -> SNS Topic: $SnsTopicArn (suscribe tu email desde la consola SNS para recibir alertas)" -ForegroundColor DarkGray

# =============================================================================
# FASE 14: VERIFICACION ACTIVA Y RESUMEN FINAL
# =============================================================================
Write-Host ""
Write-Host "[Verificacion Activa] Esperando a que los servicios ECS queden estables..." -ForegroundColor Yellow
aws ecs wait services-stable --cluster $ClusterName --services $SvcBackend $SvcFrontend 2>$null

$MaxAttempts = 20
$FrontReady = $false
$ApiReady = $false
for ($i = 1; $i -le $MaxAttempts; $i++) {
    if (-not $FrontReady) {
        try {
            $r = Invoke-WebRequest -Uri "http://$AlbDns/" -Method Get -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -eq 200) { $FrontReady = $true }
        } catch {}
    }
    if (-not $ApiReady) {
        try {
            $r = Invoke-WebRequest -Uri "http://$AlbDns/api/health" -Method Get -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -eq 200) { $ApiReady = $true }
        } catch {}
    }
    if ($FrontReady -and $ApiReady) { break }
    Write-Host "  -> Intento $i de ${MaxAttempts} - Frontend: $FrontReady | API: $ApiReady (esperando 15s)..." -ForegroundColor DarkYellow
    Start-Sleep -Seconds 15
}

Remove-Item $TmpDir -Recurse -Force -ErrorAction SilentlyContinue

$BackRunning  = aws ecs describe-services --cluster $ClusterName --services $SvcBackend  --query "services[0].runningCount" --output text 2>$null
$FrontRunning = aws ecs describe-services --cluster $ClusterName --services $SvcFrontend --query "services[0].runningCount" --output text 2>$null

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
if ($FrontReady -and $ApiReady) {
    Write-Host " DESPLIEGUE ECS FINALIZADO EXITOSAMENTE! (ServIA)     " -ForegroundColor Green -BackgroundColor Black
} else {
    Write-Host " DESPLIEGUE ECS FINALIZADO CON AVISOS (revisar logs)  " -ForegroundColor Yellow -BackgroundColor Black
}
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "CAPA 1 (PRESENTACION - FRONTEND EN FARGATE):" -ForegroundColor Yellow
Write-Host "  -> Aplicacion web:         http://$AlbDns" -ForegroundColor Green
Write-Host "  -> Servicio ECS:           $SvcFrontend ($FrontRunning tareas, min=2 max=4)" -ForegroundColor White
Write-Host "  -> Imagen:                 $ImageFrontend" -ForegroundColor DarkGray

Write-Host ""
Write-Host "CAPA 2 (APLICACION - BACKEND EN FARGATE):" -ForegroundColor Yellow
Write-Host "  -> API (via ALB /api/*):   http://$AlbDns/api/health" -ForegroundColor Green
Write-Host "  -> API directa / Swagger:  http://${AlbDns}:8000/docs" -ForegroundColor Cyan
Write-Host "  -> Servicio ECS:           $SvcBackend ($BackRunning tareas, min=2 max=4)" -ForegroundColor White
Write-Host "  -> Cluster:                $ClusterName" -ForegroundColor White
Write-Host "  -> Imagen:                 $ImageBackend" -ForegroundColor DarkGray
if (-not $ApiRuleOk) {
    Write-Host "  -> NOTA: /api/* se sirve por el proxy nginx (regla url-rewrite del ALB no disponible)" -ForegroundColor DarkYellow
}

Write-Host ""
Write-Host "CAPA 3 (DATOS - AMAZON RDS POSTGRESQL MULTI-AZ):" -ForegroundColor Yellow
Write-Host "  -> Endpoint RDS:           $RdsEndpoint" -ForegroundColor DarkGray
Write-Host "  -> Base de Datos:          servia_db (credenciales en Secrets Manager: servia/*)" -ForegroundColor DarkGray

Write-Host ""
Write-Host "DEPURACION:" -ForegroundColor Yellow
Write-Host "  -> Logs:   $LogGroupBackend | $LogGroupFront | $LogGroupDbInit" -ForegroundColor DarkGray
Write-Host "  -> Tareas detenidas: ECS > $ClusterName > Tasks > Desired status: Stopped" -ForegroundColor DarkGray
Write-Host ""
Write-Host "COSTOS: el NAT Gateway, el ALB, el RDS y las 4 tareas Fargate cobran por hora." -ForegroundColor DarkYellow
Write-Host "        Eliminalos al terminar la practica." -ForegroundColor DarkYellow
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""
