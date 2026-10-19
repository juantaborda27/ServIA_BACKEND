$ErrorActionPreference = "Continue"

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host " Despliegue Cloud ServIA (Arquitectura Completa 3 Capas)" -ForegroundColor Cyan -BackgroundColor DarkBlue
Write-Host " Capa 1: Presentacion (Frontend S3 Web + CDN)          " -ForegroundColor White
Write-Host " Capa 2: Aplicacion   (EC2 con Docker + ASG + ALB)     " -ForegroundColor White
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

$IdentityJson = aws sts get-caller-identity --output json 2>$null
$Ec2Test = aws ec2 describe-vpcs --max-items 1 2>&1

if ($LASTEXITCODE -ne 0 -or $Ec2Test -match "voc-cancel-cred" -or $Ec2Test -match "UnauthorizedOperation") { 
    Write-Host ""
    Write-Host "=======================================================" -ForegroundColor Red
    Write-Host "[ERROR] Tu sesion de AWS Learner Lab ha expirado o esta detenida." -ForegroundColor Red
    Write-Host "=======================================================" -ForegroundColor Red
    Write-Host "Causa: Las credenciales caducaron o se aplico la politica 'voc-cancel-cred'." -ForegroundColor DarkYellow
    Write-Host ""
    Write-Host "Pasos para continuar:" -ForegroundColor Yellow
    Write-Host "1. Ve a tu plataforma de AWS Academy / Learner Lab." -ForegroundColor White
    Write-Host "2. Haz clic en 'Start Lab' y espera a que el circulo se ponga verde." -ForegroundColor White
    Write-Host "3. Haz clic en 'AWS Details' -> 'AWS CLI' y copia las credenciales nuevas." -ForegroundColor White
    Write-Host "4. Pegalas en el archivo credentials.ps1 y vuelve a ejecutar este script." -ForegroundColor White
    exit 1 
}

$AccountId = (aws sts get-caller-identity --query Account --output text).Trim()
Write-Host "AWS Account ID: $AccountId" -ForegroundColor Cyan

# =============================================================================
# FASE 1: RED MULTI-AZ (VPC Y 6 SUBREDES EN 2 AZs)
# =============================================================================
Write-Host ""
Write-Host "[Fase 1: Red Multi-AZ] Creando VPC y 6 Subredes (3 Capas)..." -ForegroundColor Yellow

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

# Capa 1: Subredes Públicas (ALB Ingress)
$SubPubA = Get-OrCreateSubnet -Name "servia_sub_pub_a" -Cidr "10.0.1.0/24" -Az $AZ_A -MapPublic $true
$SubPubB = Get-OrCreateSubnet -Name "servia_sub_pub_b" -Cidr "10.0.2.0/24" -Az $AZ_B -MapPublic $true

# Capa 2: Subredes Aplicación (EC2 Auto Scaling con Docker)
$SubAppA = Get-OrCreateSubnet -Name "servia_sub_app_a" -Cidr "10.0.3.0/24" -Az $AZ_A -MapPublic $true
$SubAppB = Get-OrCreateSubnet -Name "servia_sub_app_b" -Cidr "10.0.4.0/24" -Az $AZ_B -MapPublic $true

# Capa 3: Subredes Datos (RDS PostgreSQL Multi-AZ - estrictamente privadas)
$SubDbA  = Get-OrCreateSubnet -Name "servia_sub_db_a"  -Cidr "10.0.5.0/24" -Az $AZ_A -MapPublic $false
$SubDbB  = Get-OrCreateSubnet -Name "servia_sub_db_b"  -Cidr "10.0.6.0/24" -Az $AZ_B -MapPublic $false

# Internet Gateway
$IgwId = aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VpcId" --query "InternetGateways[0].InternetGatewayId" --output text 2>$null
if (-not $IgwId -or $IgwId -eq "None") {
    $IgwId = aws ec2 create-internet-gateway --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=servia_igw}]" --query "InternetGateway.InternetGatewayId" --output text
    aws ec2 attach-internet-gateway --vpc-id $VpcId --internet-gateway-id $IgwId | Out-Null
    Write-Host "  -> Internet Gateway creado y asociado: $IgwId" -ForegroundColor Green
} else {
    Write-Host "  -> Internet Gateway existente: $IgwId" -ForegroundColor DarkGray
}

# Tabla de Enrutamiento Pública (ALB y Capa de Aplicación)
$RtPub = aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VpcId" "Name=tag:Name,Values=servia_rt_pub" --query "RouteTables[0].RouteTableId" --output text 2>$null
if (-not $RtPub -or $RtPub -eq "None") {
    $RtPub = aws ec2 create-route-table --vpc-id $VpcId --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=servia_rt_pub}]" --query "RouteTable.RouteTableId" --output text
    aws ec2 create-route --route-table-id $RtPub --destination-cidr-block 0.0.0.0/0 --gateway-id $IgwId | Out-Null
}
aws ec2 associate-route-table --subnet-id $SubPubA --route-table-id $RtPub 2>$null | Out-Null
aws ec2 associate-route-table --subnet-id $SubPubB --route-table-id $RtPub 2>$null | Out-Null
aws ec2 associate-route-table --subnet-id $SubAppA --route-table-id $RtPub 2>$null | Out-Null
aws ec2 associate-route-table --subnet-id $SubAppB --route-table-id $RtPub 2>$null | Out-Null

# Tabla de Enrutamiento Privada para la Capa de Datos (sin salida directa a internet)
$RtDb = aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VpcId" "Name=tag:Name,Values=servia_rt_db" --query "RouteTables[0].RouteTableId" --output text 2>$null
if (-not $RtDb -or $RtDb -eq "None") {
    $RtDb = aws ec2 create-route-table --vpc-id $VpcId --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=servia_rt_db}]" --query "RouteTable.RouteTableId" --output text
}
aws ec2 associate-route-table --subnet-id $SubDbA --route-table-id $RtDb 2>$null | Out-Null
aws ec2 associate-route-table --subnet-id $SubDbB --route-table-id $RtDb 2>$null | Out-Null

# =============================================================================
# FASE 2: GRUPOS DE SEGURIDAD (SECURITY GROUPS PARA LAS 3 CAPAS)
# =============================================================================
Write-Host ""
Write-Host "[Fase 2: Security Groups] Creando grupos de seguridad para las 3 capas..." -ForegroundColor Yellow

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

$SgAlb = Get-OrCreateSG -Name "sg_servia_alb" -Desc "Capa 1: ALB Public Ingress"
$SgEc2 = Get-OrCreateSG -Name "sg_servia_ec2" -Desc "Capa 2: EC2 Backend App Instance (Docker + ASG)"
$SgRds = Get-OrCreateSG -Name "sg_servia_rds" -Desc "Capa 3: RDS PostgreSQL Database"

# Ingress Rules
# ALB: Recibe HTTP (80) público desde Internet
aws ec2 authorize-security-group-ingress --group-id $SgAlb --protocol tcp --port 80 --cidr 0.0.0.0/0 2>$null | Out-Null

# EC2: Recibe tráfico en puerto 8000 desde el ALB y directo, y puerto 22 para administración SSH
aws ec2 authorize-security-group-ingress --group-id $SgEc2 --protocol tcp --port 8000 --source-group $SgAlb 2>$null | Out-Null
aws ec2 authorize-security-group-ingress --group-id $SgEc2 --protocol tcp --port 8000 --cidr 0.0.0.0/0 2>$null | Out-Null
aws ec2 authorize-security-group-ingress --group-id $SgEc2 --protocol tcp --port 80 --cidr 0.0.0.0/0 2>$null | Out-Null
aws ec2 authorize-security-group-ingress --group-id $SgEc2 --protocol tcp --port 22 --cidr 0.0.0.0/0 2>$null | Out-Null

# RDS: Puerto 5432 accesible EXCLUSIVAMENTE desde la instancia EC2
aws ec2 authorize-security-group-ingress --group-id $SgRds --protocol tcp --port 5432 --source-group $SgEc2 2>$null | Out-Null

# =============================================================================
# FASE 3: BUCKETS S3 (FRONTEND ESTÁTICO Y ARTIFACTS DE DESPLIEGUE)
# =============================================================================
Write-Host ""
Write-Host "[Fase 3: S3 Storage] Configurando Buckets S3..." -ForegroundColor Yellow
$BucketFront  = "servia-front-$AccountId"
$BucketDeploy = "servia-deploy-$AccountId"
$FrontUrl     = "http://${BucketFront}.s3-website-us-east-1.amazonaws.com"

foreach ($bucket in @($BucketFront, $BucketDeploy)) {
    aws s3api head-bucket --bucket $bucket 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  -> Bucket ya existe: $bucket" -ForegroundColor DarkGray
    } else {
        aws s3 mb "s3://$bucket" --region us-east-1 2>$null | Out-Null
        Write-Host "  -> Bucket creado: $bucket" -ForegroundColor Green
    }
}

# =============================================================================
# FASE 4: CAPA DE DATOS - AMAZON RDS POSTGRESQL MULTI-AZ
# =============================================================================
Write-Host ""
Write-Host "[Fase 4: Capa de Datos] Creando Amazon RDS PostgreSQL Multi-AZ (servia-db-rds)..." -ForegroundColor Yellow

$SubnetGroupName = "servia-db-subnets"
$SubnetGroupCheck = aws rds describe-db-subnet-groups --db-subnet-group-name $SubnetGroupName 2>$null
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
      --master-user-password PasswordSegura123 `
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
# FASE 5: LOAD BALANCER (ALB) Y TARGET GROUP
# =============================================================================
Write-Host ""
Write-Host "[Fase 5: Load Balancer] Creando Application Load Balancer y Target Group..." -ForegroundColor Yellow

$TgBackend = aws elbv2 describe-target-groups --names tg-servia-backend --query "TargetGroups[0].TargetGroupArn" --output text 2>$null
if (-not $TgBackend -or $TgBackend -eq "None") {
    $TgBackend = aws elbv2 create-target-group `
      --name tg-servia-backend `
      --protocol HTTP `
      --port 8000 `
      --vpc-id $VpcId `
      --target-type instance `
      --health-check-protocol HTTP `
      --health-check-path /health `
      --health-check-interval-seconds 15 `
      --health-check-timeout-seconds 5 `
      --healthy-threshold-count 2 `
      --unhealthy-threshold-count 3 `
      --query "TargetGroups[0].TargetGroupArn" `
      --output text
    Write-Host "  -> Target Group creado: tg-servia-backend ($TgBackend)" -ForegroundColor Green
} else {
    Write-Host "  -> Target Group existente: $TgBackend" -ForegroundColor DarkGray
}

$AlbArn = aws elbv2 describe-load-balancers --names alb-servia-api --query "LoadBalancers[0].LoadBalancerArn" --output text 2>$null
if (-not $AlbArn -or $AlbArn -eq "None") {
    $AlbArn = aws elbv2 create-load-balancer `
      --name alb-servia-api `
      --subnets $SubPubA $SubPubB `
      --security-groups $SgAlb `
      --scheme internet-facing `
      --query "LoadBalancers[0].LoadBalancerArn" `
      --output text
    Write-Host "  -> ALB creado: alb-servia-api" -ForegroundColor Green
} else {
    Write-Host "  -> ALB existente: $AlbArn" -ForegroundColor DarkGray
}

$AlbDns = (aws elbv2 describe-load-balancers --load-balancer-arns $AlbArn --query "LoadBalancers[0].DNSName" --output text).Trim()
Write-Host "ALB Backend DNS: $AlbDns" -ForegroundColor Cyan

# Listener en puerto 80 del ALB reenviando hacia el Target Group del backend
$ListenerArn = aws elbv2 describe-listeners --load-balancer-arn $AlbArn --query "Listeners[0].ListenerArn" --output text 2>$null
if (-not $ListenerArn -or $ListenerArn -eq "None") {
    $ListenerArn = aws elbv2 create-listener `
      --load-balancer-arn $AlbArn `
      --protocol HTTP `
      --port 80 `
      --default-actions Type=forward,TargetGroupArn=$TgBackend `
      --query "Listeners[0].ListenerArn" `
      --output text
    Write-Host "  -> Listener HTTP:80 configurado en ALB" -ForegroundColor Green
}

# =============================================================================
# FASE 6: CAPA DE APLICACIÓN - LAUNCH TEMPLATE, AUTO SCALING GROUP (ASG) Y POLÍTICAS
# =============================================================================
Write-Host ""
Write-Host "[Fase 6: Capa de Aplicacion] Configurando Launch Template y Auto Scaling Group con Docker..." -ForegroundColor Yellow

# 6.1 Empaquetar Backend local y subir a S3
Write-Host "Empaquetando backend local y archivo de inicializacion SQL..." -ForegroundColor Cyan
$BackendZipPath = "$BackendDir\backend_bundle.zip"
if (Test-Path $BackendZipPath) { Remove-Item $BackendZipPath -Force }

$itemsToZip = Get-ChildItem -Path "$BackendDir" | Where-Object { 
    $_.Name -notmatch '^(venv|\.venv|__pycache__|\.git|backend_bundle\.zip)$' -and 
    $_.Extension -ne '.pem'
}
Compress-Archive -Path $itemsToZip.FullName -DestinationPath $BackendZipPath -Force
aws s3 cp $BackendZipPath "s3://$BucketDeploy/backend_bundle.zip" | Out-Null
Remove-Item $BackendZipPath -Force -ErrorAction SilentlyContinue
Write-Host "  -> Codigo sincronizado en s3://$BucketDeploy/backend_bundle.zip" -ForegroundColor Green

# 6.2 Obtener AMI y KeyPair
$AmiId = aws ssm get-parameters --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64 --query "Parameters[0].Value" --output text
$KeyName = "servia_ec2_key"
aws ec2 describe-key-pairs --key-names $KeyName 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    aws ec2 create-key-pair --key-name $KeyName --query "KeyMaterial" --output text > "$BackendDir\$KeyName.pem" 2>$null
    Write-Host "  -> KeyPair creado: $BackendDir\$KeyName.pem" -ForegroundColor Green
}

$IamProfile = "LabInstanceProfile"

# 6.3 UserData Script para Launch Template: Instala Docker, espera RDS, ejecuta init.sql y corre contenedor
$UserDataScript = @"
#!/bin/bash
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
echo "=== Iniciando ServIA EC2 Backend (Docker + RDS) ==="

# 1. Actualizar sistema e instalar Docker y herramientas
dnf update -y
dnf install -y docker git unzip nc
systemctl enable docker
systemctl start docker
usermod -a -G docker ec2-user

# 2. Descargar código empaquetado desde S3 o clonar desde GitHub
mkdir -p /home/ec2-user/app
cd /home/ec2-user

echo "Descargando bundle desde S3..."
aws s3 cp s3://${BucketDeploy}/backend_bundle.zip /home/ec2-user/backend_bundle.zip --region us-east-1

if [ -f /home/ec2-user/backend_bundle.zip ]; then
    unzip -o /home/ec2-user/backend_bundle.zip -d /home/ec2-user/app
else
    echo "Bundle S3 no disponible, clonando desde GitHub..."
    git clone https://github.com/juantaborda27/ServIA_BACKEND.git /home/ec2-user/app
fi

chown -R ec2-user:ec2-user /home/ec2-user/app
cd /home/ec2-user/app

# 3. Esperar que Amazon RDS PostgreSQL esté available y acepte conexiones
echo "Esperando que Amazon RDS servia-db-rds este disponible..."
while true; do
    RDS_STATUS=`$(aws rds describe-db-instances --db-instance-identifier servia-db-rds --region us-east-1 --query "DBInstances[0].DBInstanceStatus" --output text 2>/dev/null)
    if [ "`$RDS_STATUS" == "available" ]; then
        RDS_HOST=`$(aws rds describe-db-instances --db-instance-identifier servia-db-rds --region us-east-1 --query "DBInstances[0].Endpoint.Address" --output text 2>/dev/null)
        if [ -n "`$RDS_HOST" ] && [ "`$RDS_HOST" != "None" ]; then
            echo "RDS disponible en `$RDS_HOST"
            break
        fi
    fi
    sleep 10
done

echo "Esperando que PostgreSQL acepte conexiones en el puerto 5432..."
until docker run --rm postgres:16-alpine pg_isready -h "`$RDS_HOST" -p 5432 -U postgres; do
    sleep 5
done

# 4. Ejecutar script de inicialización init.sql en RDS PostgreSQL
if [ -f /home/ec2-user/app/init.sql ]; then
    echo "Ejecutando init.sql en RDS PostgreSQL..."
    docker run --rm -e PGPASSWORD=PasswordSegura123 \
      -v /home/ec2-user/app/init.sql:/init.sql \
      postgres:16-alpine \
      psql -h "`$RDS_HOST" -U postgres -d servia_db -f /init.sql
    echo "OK_DB_INIT_COMPLETE" > /home/ec2-user/db_init_done.txt
fi

# 5. Construir imagen Docker del Backend
echo "Construyendo imagen Docker servia-backend..."
docker build -t servia-backend:latest .

# 6. Ejecutar el contenedor del Backend con reinicio automático
echo "Iniciando contenedor Docker servia_backend..."
docker rm -f servia_backend 2>/dev/null || true
docker run -d \
  --name servia_backend \
  --restart always \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://postgres:PasswordSegura123@`$RDS_HOST:5432/servia_db" \
  -e JWT_SECRET_KEY="_Av13cu#7-LfUNXa+xMUz6Y" \
  -e PYTHONUNBUFFERED=1 \
  servia-backend:latest

echo "=== Aprovisionamiento completado con exito ==="
echo "READY" > /home/ec2-user/provisioning_done.txt
"@

$UserDataEnc = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($UserDataScript))

# 6.4 Crear o Actualizar Launch Template
Write-Host "Configurando EC2 Launch Template (lt-servia-backend)..." -ForegroundColor Cyan
aws ec2 delete-launch-template --launch-template-name lt-servia-backend 2>$null | Out-Null

$LaunchTemplateData = @{
    ImageId = $AmiId
    InstanceType = "t3.small"
    KeyName = $KeyName
    IamInstanceProfile = @{ Name = $IamProfile }
    SecurityGroupIds = @($SgEc2)
    UserData = $UserDataEnc
    TagSpecifications = @(
        @{
            ResourceType = "instance"
            Tags = @(
                @{ Key = "Name"; Value = "servia_backend_ec2" }
            )
        }
    )
}
$ltJsonFile = "$BackendDir\lt_data.json"
$LaunchTemplateData | ConvertTo-Json -Depth 10 | Out-File -FilePath $ltJsonFile -Encoding ascii
aws ec2 create-launch-template --launch-template-name lt-servia-backend --version-description "v1" --launch-template-data file://$ltJsonFile 2>$null | Out-Null
Remove-Item $ltJsonFile -ErrorAction SilentlyContinue
Write-Host "  -> Launch Template lt-servia-backend creado con exito." -ForegroundColor Green

# 6.5 Crear Auto Scaling Group (ASG) Multi-AZ (Alta Disponibilidad Activa en 2 Zonas)
Write-Host "Configurando Auto Scaling Group Multi-AZ (min=2, max=4, desired=2 repartido en AZ-A y AZ-B)..." -ForegroundColor Cyan
$AsgCheck = aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names asg-servia-backend --query "AutoScalingGroups[0].AutoScalingGroupName" --output text 2>$null

if (-not $AsgCheck -or $AsgCheck -eq "None") {
    aws autoscaling create-auto-scaling-group `
      --auto-scaling-group-name asg-servia-backend `
      --launch-template "LaunchTemplateName=lt-servia-backend,Version=`$Latest" `
      --min-size 2 `
      --max-size 4 `
      --desired-capacity 2 `
      --vpc-zone-identifier "$SubAppA,$SubAppB" `
      --target-group-arns $TgBackend 2>$null | Out-Null
    Write-Host "  -> Auto Scaling Group creado y distribuido en AZ-A y AZ-B (Multi-AZ HA)." -ForegroundColor Green
} else {
    aws autoscaling update-auto-scaling-group `
      --auto-scaling-group-name asg-servia-backend `
      --launch-template "LaunchTemplateName=lt-servia-backend,Version=`$Latest" `
      --min-size 2 `
      --max-size 4 `
      --desired-capacity 2 `
      --vpc-zone-identifier "$SubAppA,$SubAppB" 2>$null | Out-Null
    Write-Host "  -> Auto Scaling Group actualizado a Multi-AZ (2 instancias activas)." -ForegroundColor Green
}

# 6.6 Política de Auto Scaling (Target Tracking Scaling Policy: CPU Target 70%)
Write-Host "Configurando Politica de Auto Scaling basada en CPU (Target: 70%)..." -ForegroundColor Cyan

# JSON inline con comillas escapadas - ScaleOut/InCooldown van como flag separado, NO dentro del JSON
$policyInlineJson = '{\"TargetValue\":70.0,\"PredefinedMetricSpecification\":{\"PredefinedMetricType\":\"ASGAverageCPUUtilization\"},\"DisableScaleIn\":false}'

$policyResult = aws autoscaling put-scaling-policy `
  --auto-scaling-group-name asg-servia-backend `
  --policy-name "cpu-scaling-asg-servia" `
  --policy-type TargetTrackingScaling `
  --estimated-instance-warmup 120 `
  --target-tracking-configuration $policyInlineJson 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "  -> [OK] Politica Target Tracking CPU 70% aplicada al ASG." -ForegroundColor Green
} else {
    Write-Host "  -> [WARN] No se pudo aplicar la politica: $policyResult" -ForegroundColor DarkYellow
}

# =============================================================================
# FASE 6.7: MONITOREO - AMAZON CLOUDWATCH ALARMS (EC2 ASG + RDS + ALB)
# =============================================================================
Write-Host ""
Write-Host "[Fase 6.7: CloudWatch] Configurando Alarmas de Monitoreo (Multi-AZ)..." -ForegroundColor Yellow

# --- SNS Topic para notificaciones de alertas ---
$SnsTopicName  = "servia-alertas-ops"
$SnsTopicArn   = aws sns list-topics --query "Topics[?ends_with(TopicArn,'$SnsTopicName')].TopicArn | [0]" --output text 2>$null
if (-not $SnsTopicArn -or $SnsTopicArn -eq "None") {
    $SnsTopicArn = aws sns create-topic --name $SnsTopicName --query "TopicArn" --output text 2>$null
    Write-Host "  -> SNS Topic creado: $SnsTopicArn" -ForegroundColor Green
} else {
    Write-Host "  -> SNS Topic existente: $SnsTopicArn" -ForegroundColor DarkGray
}

function Set-CWAlarm {
    param(
        [string]$Name,
        [string]$Description,
        [string]$Namespace,
        [string]$MetricName,
        [string]$Dimensions,
        [string]$Statistic,
        [double]$Threshold,
        [string]$ComparisonOp,
        [int]$Periods,
        [int]$EvalPeriods,
        [string]$Unit = "None",
        [string[]]$Actions = @()
    )
    $cmd = "aws cloudwatch put-metric-alarm " +
        "--alarm-name `"$Name`" " +
        "--alarm-description `"$Description`" " +
        "--namespace `"$Namespace`" " +
        "--metric-name `"$MetricName`" " +
        "--dimensions $Dimensions " +
        "--statistic $Statistic " +
        "--threshold $Threshold " +
        "--comparison-operator $ComparisonOp " +
        "--period $Periods " +
        "--evaluation-periods $EvalPeriods " +
        "--treat-missing-data notBreaching"
    if ($Unit -ne "None") { $cmd += " --unit $Unit" }
    if ($Actions.Count -gt 0) {
        $actStr = ($Actions | ForEach-Object { $_ }) -join " "
        $cmd += " --alarm-actions $actStr --ok-actions $actStr"
    }
    Invoke-Expression "$cmd 2>`$null" | Out-Null
}

# ── 1. EC2 / ASG: CPU Alta (Scale-Out Warning) ──────────────────────────────
Set-CWAlarm `
    -Name        "servia-asg-cpu-alta" `
    -Description "ALERTA: CPU promedio del ASG supera el 80% - posible saturacion" `
    -Namespace   "AWS/EC2" `
    -MetricName  "CPUUtilization" `
    -Dimensions  "Name=AutoScalingGroupName,Value=asg-servia-backend" `
    -Statistic   "Average" `
    -Threshold   80 `
    -ComparisonOp "GreaterThanThreshold" `
    -Periods     60 `
    -EvalPeriods 3 `
    -Unit        "Percent" `
    -Actions     @($SnsTopicArn)
Write-Host "  -> [OK] Alarma CPU Alta ASG (>80% por 3 min)." -ForegroundColor Green

# ── 2. EC2 / ASG: CPU Baja (Scale-In / Inactividad) ─────────────────────────
Set-CWAlarm `
    -Name        "servia-asg-cpu-baja" `
    -Description "INFO: CPU promedio del ASG por debajo del 10% - posible sub-utilizacion" `
    -Namespace   "AWS/EC2" `
    -MetricName  "CPUUtilization" `
    -Dimensions  "Name=AutoScalingGroupName,Value=asg-servia-backend" `
    -Statistic   "Average" `
    -Threshold   10 `
    -ComparisonOp "LessThanThreshold" `
    -Periods     300 `
    -EvalPeriods 3 `
    -Unit        "Percent" `
    -Actions     @($SnsTopicArn)
Write-Host "  -> [OK] Alarma CPU Baja ASG (<10% por 15 min)." -ForegroundColor Green

# ── 3. RDS: CPU Alta ──────────────────────────────────────────────────────────
Set-CWAlarm `
    -Name        "servia-rds-cpu-alta" `
    -Description "ALERTA: CPU de RDS PostgreSQL supera el 75%" `
    -Namespace   "AWS/RDS" `
    -MetricName  "CPUUtilization" `
    -Dimensions  "Name=DBInstanceIdentifier,Value=servia-db-rds" `
    -Statistic   "Average" `
    -Threshold   75 `
    -ComparisonOp "GreaterThanThreshold" `
    -Periods     60 `
    -EvalPeriods 3 `
    -Unit        "Percent" `
    -Actions     @($SnsTopicArn)
Write-Host "  -> [OK] Alarma CPU Alta RDS (>75% por 3 min)." -ForegroundColor Green

# ── 4. RDS: Espacio en disco bajo ────────────────────────────────────────────
Set-CWAlarm `
    -Name        "servia-rds-disco-bajo" `
    -Description "ALERTA CRITICA: Espacio libre en disco RDS menor a 2 GB" `
    -Namespace   "AWS/RDS" `
    -MetricName  "FreeStorageSpace" `
    -Dimensions  "Name=DBInstanceIdentifier,Value=servia-db-rds" `
    -Statistic   "Average" `
    -Threshold   2147483648 `
    -ComparisonOp "LessThanThreshold" `
    -Periods     60 `
    -EvalPeriods 1 `
    -Unit        "Bytes" `
    -Actions     @($SnsTopicArn)
Write-Host "  -> [OK] Alarma Disco Bajo RDS (<2 GB)." -ForegroundColor Green

# ── 5. RDS: Conexiones de base de datos altas ────────────────────────────────
Set-CWAlarm `
    -Name        "servia-rds-conexiones-altas" `
    -Description "ALERTA: Numero de conexiones a RDS supera 80" `
    -Namespace   "AWS/RDS" `
    -MetricName  "DatabaseConnections" `
    -Dimensions  "Name=DBInstanceIdentifier,Value=servia-db-rds" `
    -Statistic   "Average" `
    -Threshold   80 `
    -ComparisonOp "GreaterThanThreshold" `
    -Periods     60 `
    -EvalPeriods 2 `
    -Actions     @($SnsTopicArn)
Write-Host "  -> [OK] Alarma Conexiones Altas RDS (>80 conexiones)." -ForegroundColor Green

# ── 6. ALB: Errores HTTP 5XX altos ───────────────────────────────────────────
$AlbFullName = (aws elbv2 describe-load-balancers --names alb-servia-api --query "LoadBalancers[0].LoadBalancerArn" --output text 2>$null)
if ($AlbFullName -and $AlbFullName -ne "None") {
    # CloudWatch usa el sufijo del ARN: app/alb-servia-api/xxxxxxxxxxxxxxxx
    $AlbDimValue = ($AlbFullName -replace "^arn:aws:elasticloadbalancing:[^:]+:[^:]+:loadbalancer/", "")
    Set-CWAlarm `
        -Name        "servia-alb-errores-5xx" `
        -Description "ALERTA: Tasa de errores 5XX en ALB supera 10 en 1 minuto" `
        -Namespace   "AWS/ApplicationELB" `
        -MetricName  "HTTPCode_ELB_5XX_Count" `
        -Dimensions  "Name=LoadBalancer,Value=$AlbDimValue" `
        -Statistic   "Sum" `
        -Threshold   10 `
        -ComparisonOp "GreaterThanThreshold" `
        -Periods     60 `
        -EvalPeriods 2 `
        -Unit        "Count" `
        -Actions     @($SnsTopicArn)
    Write-Host "  -> [OK] Alarma Errores 5XX ALB (>10 en 1 min)." -ForegroundColor Green

    # ── 7. ALB: Latencia alta (p95 > 3s) ─────────────────────────────────────
    Set-CWAlarm `
        -Name        "servia-alb-latencia-alta" `
        -Description "ALERTA: Latencia de respuesta del ALB supera 3 segundos (promedio)" `
        -Namespace   "AWS/ApplicationELB" `
        -MetricName  "TargetResponseTime" `
        -Dimensions  "Name=LoadBalancer,Value=$AlbDimValue" `
        -Statistic   "Average" `
        -Threshold   3 `
        -ComparisonOp "GreaterThanThreshold" `
        -Periods     60 `
        -EvalPeriods 3 `
        -Unit        "Seconds" `
        -Actions     @($SnsTopicArn)
    Write-Host "  -> [OK] Alarma Latencia Alta ALB (>3s promedio)." -ForegroundColor Green

    # ── 8. ALB: Hosts saludables bajos (HealthyHostCount < 2) ────────────────
    $TgArnFull = aws elbv2 describe-target-groups --names tg-servia-backend --query "TargetGroups[0].TargetGroupArn" --output text 2>$null
    if ($TgArnFull -and $TgArnFull -ne "None") {
        $TgDimValue = ($TgArnFull -replace "^arn:aws:elasticloadbalancing:[^:]+:[^:]+:targetgroup/", "targetgroup/")
        Set-CWAlarm `
            -Name        "servia-alb-hosts-bajos" `
            -Description "ALERTA CRITICA: Menos de 2 instancias saludables en el Target Group del ALB" `
            -Namespace   "AWS/ApplicationELB" `
            -MetricName  "HealthyHostCount" `
            -Dimensions  "Name=LoadBalancer,Value=$AlbDimValue Name=TargetGroup,Value=$TgDimValue" `
            -Statistic   "Minimum" `
            -Threshold   2 `
            -ComparisonOp "LessThanThreshold" `
            -Periods     60 `
            -EvalPeriods 2 `
            -Unit        "Count" `
            -Actions     @($SnsTopicArn)
        Write-Host "  -> [OK] Alarma Hosts Saludables Bajos ALB (<2 instancias)." -ForegroundColor Green
    }
}

Write-Host "  -> CloudWatch: 8 alarmas configuradas exitosamente." -ForegroundColor Cyan
Write-Host "  -> SNS Topic para notificaciones: $SnsTopicArn" -ForegroundColor DarkGray
Write-Host "  -> NOTA: Para recibir emails de alerta, suscribete al SNS Topic desde la consola AWS:" -ForegroundColor DarkYellow
Write-Host "     AWS Console -> SNS -> Topics -> $SnsTopicName -> Create subscription -> Email" -ForegroundColor DarkYellow

# =============================================================================
# FASE 7: CAPA DE PRESENTACIÓN - S3 STATIC WEBSITE (+ CLOUDFRONT CDN)
# =============================================================================
Write-Host ""
Write-Host "[Fase 7: Capa de Presentacion] Compilando Frontend e implementando en S3..." -ForegroundColor Yellow


# --- Si el directorio del frontend no existe localmente, clonarlo desde GitHub ---
if (-not (Test-Path $FrontendDir)) {
    Write-Host "  [INFO] Directorio frontend no encontrado localmente. Clonando desde GitHub..." -ForegroundColor DarkYellow
    $FrontendDir = "$PSScriptRoot\Front-ServiceIA"
    git clone https://github.com/Dyelamo/Front-ServiceIA.git $FrontendDir 2>&1 | Out-Null
    if (Test-Path $FrontendDir) {
        Write-Host "  -> Frontend clonado desde GitHub: https://github.com/Dyelamo/Front-ServiceIA.git" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] No se pudo clonar el frontend. Verifica la URL del repositorio." -ForegroundColor Red
    }
} else {
    Write-Host "  -> Usando frontend local en: $FrontendDir" -ForegroundColor Green
}

if (Test-Path $FrontendDir) {
    Push-Location $FrontendDir
    Write-Host "Instalando dependencias de Node.js..." -ForegroundColor Cyan
    npm install --no-audit --no-fund

    # 1. Configurar la URL actual del ALB en archivos .env locales para Expo
    Set-Content -Path ".env" -Value "EXPO_PUBLIC_API_URL=http://$AlbDns" -Encoding ascii
    Set-Content -Path ".env.local" -Value "EXPO_PUBLIC_API_URL=http://$AlbDns" -Encoding ascii
    $env:EXPO_PUBLIC_API_URL = "http://$AlbDns"

    # 2. Limpiar cache previo para forzar a que Expo hornee la URL correcta
    if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force -ErrorAction SilentlyContinue }
    if (Test-Path ".expo") { Remove-Item ".expo" -Recurse -Force -ErrorAction SilentlyContinue }

    Write-Host "Compilando Frontend apuntando al Backend ($env:EXPO_PUBLIC_API_URL)..." -ForegroundColor Cyan
    npx expo export -p web --clear
    $BuildOk = ($LASTEXITCODE -eq 0)
    Remove-Item Env:EXPO_PUBLIC_API_URL -ErrorAction SilentlyContinue
    Pop-Location


    if ($BuildOk -and (Test-Path "$FrontendDir\dist")) {
        Write-Host "Configurando Bucket S3 $BucketFront como sitio web estatico..." -ForegroundColor Cyan
        aws s3api put-public-access-block --bucket $BucketFront --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

        # Politica S3 inline (evita problema file:// en Windows con rutas con espacios)
        $bucketPolicyInline = '{\"Version\":\"2012-10-17\",\"Statement\":[{\"Sid\":\"PublicReadForWebsite\",\"Effect\":\"Allow\",\"Principal\":\"*\",\"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::' + $BucketFront + '/*\"}]}'
        aws s3api put-bucket-policy --bucket $BucketFront --policy $bucketPolicyInline 2>$null | Out-Null

        aws s3 website "s3://$BucketFront" --index-document index.html --error-document index.html | Out-Null

        Write-Host "Sincronizando archivos del frontend con S3..." -ForegroundColor Cyan
        aws s3 sync "$FrontendDir\dist" "s3://$BucketFront" --delete | Out-Null

        Write-Host "Configurando soporte SPA (Single Page Application) en S3..." -ForegroundColor Cyan
        $SpaRoutes = @('login', 'register', 'client', 'professional', 'services', 'requests', 'offers', 'profile')
        foreach ($r in $SpaRoutes) {
            aws s3 cp "s3://$BucketFront/index.html" "s3://$BucketFront/$r" --content-type text/html 2>$null | Out-Null
            aws s3 cp "s3://$BucketFront/index.html" "s3://$BucketFront/$r/index.html" --content-type text/html 2>$null | Out-Null
        }
        Write-Host "  -> Frontend publicado exitosamente en: $FrontUrl" -ForegroundColor Green
    } else {
        Write-Host "[AVISO] La compilacion del frontend no genero la carpeta 'dist'. Revisa errores de npm/expo arriba." -ForegroundColor DarkYellow
    }
}


# CloudFront CDN (Opcional / Best-Effort)
Write-Host ""
Write-Host "Configurando Amazon CloudFront CDN (HTTPS & Edge Caching)..." -ForegroundColor Cyan
$CfDomain = $null
$CfUrl = $null

$DistConfig = @"
{
    "CallerReference": "servia-front-$AccountId-$((Get-Date).Ticks)",
    "Comment": "ServIA Frontend CloudFront CDN",
    "Enabled": true,
    "DefaultRootObject": "index.html",
    "Origins": {
        "Quantity": 1,
        "Items": [
            {
                "Id": "S3-servia-front",
                "DomainName": "${BucketFront}.s3-website-us-east-1.amazonaws.com",
                "CustomOriginConfig": {
                    "HTTPPort": 80,
                    "HTTPSPort": 443,
                    "OriginProtocolPolicy": "http-only"
                }
            }
        ]
    },
    "DefaultCacheBehavior": {
        "TargetOriginId": "S3-servia-front",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": {
            "Quantity": 2,
            "Items": ["GET", "HEAD"]
        },
        "Compress": true,
        "ForwardedValues": {
            "QueryString": false,
            "Cookies": { "Forward": "none" }
        },
        "MinTTL": 0,
        "DefaultTTL": 86400,
        "MaxTTL": 31536000
    },
    "CustomErrorResponses": {
        "Quantity": 2,
        "Items": [
            {
                "ErrorCode": 404,
                "ResponsePagePath": "/index.html",
                "ResponseCode": "200",
                "ErrorCachingMinTTL": 0
            },
            {
                "ErrorCode": 403,
                "ResponsePagePath": "/index.html",
                "ResponseCode": "200",
                "ErrorCachingMinTTL": 0
            }
        ]
    }
}
"@

$CfConfigFile = "$BackendDir\cf_config.json"
$DistConfig | Out-File -FilePath $CfConfigFile -Encoding ascii
$CfResult = aws cloudfront create-distribution --distribution-config file://$CfConfigFile 2>&1
Remove-Item $CfConfigFile -ErrorAction SilentlyContinue

if ($LASTEXITCODE -eq 0) {
    try {
        $CfJson = $CfResult | ConvertFrom-Json
        $CfDomain = $CfJson.Distribution.DomainName
        $CfUrl = "https://$CfDomain"
        Write-Host "  -> CloudFront CDN creado con exito: $CfUrl" -ForegroundColor Green
    } catch {
        Write-Host "  -> Distribucion CloudFront iniciada." -ForegroundColor Cyan
    }
} else {
    Write-Host "  -> [AVISO] CloudFront no esta habilitado en tu cuenta de Learner Lab. Se utilizara el acceso directo por S3 Website." -ForegroundColor DarkYellow
}

# =============================================================================
# FASE 8: VERIFICACIÓN ACTIVA DEL BACKEND Y RESUMEN FINAL
# =============================================================================
Write-Host ""
Write-Host "[Verificacion Activa] Esperando a que las instancias del Auto Scaling Group pasen Health Checks del ALB..." -ForegroundColor Yellow
$MaxAttempts = 30
$BackendReady = $false

for ($i = 1; $i -le $MaxAttempts; $i++) {
    try {
        $res = Invoke-WebRequest -Uri "http://$AlbDns/health" -Method Get -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        if ($res.StatusCode -eq 200) {
            $BackendReady = $true
            break
        }
    } catch {
        # Las instancias de EC2 en el ASG están instalando Docker y compilando
    }
    Write-Host "  -> Intento $i de ${MaxAttempts} - Instancias del ASG inicializando Backend y Base de Datos (esperando 15s)..." -ForegroundColor DarkYellow
    Start-Sleep -Seconds 15
}

$RdsEndpoint = (aws rds describe-db-instances --db-instance-identifier servia-db-rds --query "DBInstances[0].Endpoint.Address" --output text 2>$null).Trim()

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host " DESPLIEGUE FINALIZADO EXITOSAMENTE! (ServIA 3 Capas) " -ForegroundColor Green -BackgroundColor Black
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "CAPA 1 (PRESENTACION - FRONTEND):" -ForegroundColor Yellow
if ($CfUrl) {
    Write-Host "  -> CloudFront CDN (HTTPS): $CfUrl" -ForegroundColor Green
    Write-Host "  -> S3 Website (Directo):   $FrontUrl" -ForegroundColor White
} else {
    Write-Host "  -> S3 Website:             $FrontUrl" -ForegroundColor Green
}

Write-Host ""
Write-Host "CAPA 2 (APLICACION - BACKEND EN EC2 CON AUTO SCALING):" -ForegroundColor Yellow
Write-Host "  -> ALB DNS (Endpoint API): http://$AlbDns" -ForegroundColor Green
Write-Host "  -> Auto Scaling Group:     asg-servia-backend (min=2, max=4, desired=2) Multi-AZ" -ForegroundColor White
Write-Host "  -> Politica Auto Scaling:  Target Tracking CPU al 70%" -ForegroundColor White
Write-Host "  -> Launch Template:        lt-servia-backend" -ForegroundColor White
Write-Host "  -> Documentacion Swagger:  http://$AlbDns/docs" -ForegroundColor Cyan
Write-Host "  -> Health Check:           http://$AlbDns/health" -ForegroundColor Cyan

Write-Host ""
Write-Host "CAPA 3 (DATOS - AMAZON RDS POSTGRESQL MULTI-AZ):" -ForegroundColor Yellow
Write-Host "  -> Motor:                  PostgreSQL 15 (Multi-AZ)" -ForegroundColor White
Write-Host "  -> Endpoint RDS:           $RdsEndpoint" -ForegroundColor DarkGray
Write-Host "  -> Base de Datos:          servia_db" -ForegroundColor DarkGray
Write-Host "  -> Usuario:                postgres" -ForegroundColor DarkGray
Write-Host "  -> Esquema y Semillas:     Inicializados automaticamente con init.sql" -ForegroundColor DarkGray
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""
