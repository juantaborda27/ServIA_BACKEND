$ErrorActionPreference = "Continue"

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host " Iniciando Destruccion Cloud ServIA (3 Capas Completas)" -ForegroundColor Cyan -BackgroundColor DarkRed
Write-Host "=======================================================" -ForegroundColor Cyan

# 1. Cargar Credenciales de AWS Learner Lab
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

$IdentityJson = aws sts get-caller-identity --output json 2>$null
$Ec2Test = aws ec2 describe-vpcs --max-items 1 2>&1

if ($LASTEXITCODE -ne 0 -or $Ec2Test -match "voc-cancel-cred" -or $Ec2Test -match "UnauthorizedOperation") { 
    Write-Host ""
    Write-Host "=======================================================" -ForegroundColor Red
    Write-Host "[ERROR] Tu sesion de AWS Learner Lab ha expirado o esta detenida." -ForegroundColor Red
    Write-Host "=======================================================" -ForegroundColor Red
    Write-Host "Causa: Las credenciales caducaron o se aplico la politica 'voc-cancel-cred'." -ForegroundColor DarkYellow
    Write-Host "Por favor actualiza credentials.ps1 con credenciales nuevas." -ForegroundColor Yellow
    exit 1 
}

$AccountId = (aws sts get-caller-identity --query Account --output text 2>$null).Trim()
Write-Host "AWS Account ID: $AccountId" -ForegroundColor Cyan

function Release-ElasticIPs {
    Write-Host ""
    Write-Host "[Redes] Buscando y liberando IPs Elasticas (evitar limite de 5 EIPs en Learner Lab)..." -ForegroundColor Yellow
    $retry = 0
    while ($retry -lt 8) {
        $AllIps = aws ec2 describe-addresses --query "Addresses[*].AllocationId" --output text 2>$null
        $allocatedList = @($AllIps -split '\s+' | Where-Object { $_ -match '^eipalloc-' })
        if ($allocatedList.Count -eq 0) {
            Write-Host "  -> No hay IPs Elasticas asignadas en la cuenta." -ForegroundColor Green
            break
        }
        $freedCount = 0
        foreach ($IpAlloc in $allocatedList) {
            $AssocId = aws ec2 describe-addresses --allocation-ids $IpAlloc --query "Addresses[0].AssociationId" --output text 2>$null
            if ($AssocId -and $AssocId -ne "None" -and $AssocId -match '^eipassoc-') {
                aws ec2 disassociate-address --association-id $AssocId 2>$null | Out-Null
            }
            aws ec2 release-address --allocation-id $IpAlloc 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  -> IP Elastica liberada con exito: $IpAlloc" -ForegroundColor Green
                $freedCount++
            }
        }
        $retry++
        if ($freedCount -eq $allocatedList.Count) { break }
        Start-Sleep -Seconds 5
    }
}

# =============================================================================
# FASE 1: SOLICITAR ELIMINACIÓN ASÍNCRONA DE AMAZON RDS
# =============================================================================
Write-Host ""
Write-Host "[Fase 1: RDS] Solicitando eliminacion de Amazon RDS PostgreSQL (en segundo plano)..." -ForegroundColor Yellow
$RdsInstances = @("servia-db-rds")
foreach ($rdsId in $RdsInstances) {
    $RdsStatus = aws rds describe-db-instances --db-instance-identifier $rdsId --query "DBInstances[0].DBInstanceStatus" --output text 2>$null
    if ($RdsStatus -and $RdsStatus -ne "None" -and $RdsStatus.Trim() -ne "") {
        $RdsStatus = $RdsStatus.Trim()
        if ($RdsStatus -ne "deleting") {
            Write-Host "  -> Solicitando delete-db-instance para $rdsId (sin snapshot final)..." -ForegroundColor Cyan
            aws rds delete-db-instance --db-instance-identifier $rdsId --skip-final-snapshot --delete-automated-backups 2>$null | Out-Null
        } else {
            Write-Host "  -> $rdsId ya se encuentra en proceso de eliminacion." -ForegroundColor DarkGray
        }
    }
}

# =============================================================================
# FASE 1.5: ELIMINAR ALARMAS CLOUDWATCH Y SNS TOPIC
# =============================================================================
Write-Host ""
Write-Host "[Fase 1.5: CloudWatch] Eliminando Alarmas de Monitoreo y SNS Topic..." -ForegroundColor Yellow

$CwAlarms = @(
    "servia-asg-cpu-alta",
    "servia-asg-cpu-baja",
    "servia-rds-cpu-alta",
    "servia-rds-disco-bajo",
    "servia-rds-conexiones-altas",
    "servia-alb-errores-5xx",
    "servia-alb-latencia-alta",
    "servia-alb-hosts-bajos"
)
aws cloudwatch delete-alarms --alarm-names $CwAlarms 2>$null | Out-Null
Write-Host "  -> Alarmas CloudWatch eliminadas." -ForegroundColor Green

$SnsTopicArn = aws sns list-topics --query "Topics[?ends_with(TopicArn,'servia-alertas-ops')].TopicArn | [0]" --output text 2>$null
if ($SnsTopicArn -and $SnsTopicArn -ne "None" -and $SnsTopicArn.Trim() -ne "") {
    aws sns delete-topic --topic-arn $SnsTopicArn 2>$null | Out-Null
    Write-Host "  -> SNS Topic 'servia-alertas-ops' eliminado." -ForegroundColor Green
} else {
    Write-Host "  -> SNS Topic no encontrado (ya eliminado)." -ForegroundColor DarkGray
}

# =============================================================================
# FASE 2: ELIMINAR AUTO SCALING GROUP Y LAUNCH TEMPLATES
# =============================================================================
Write-Host ""
Write-Host "[Fase 2: Auto Scaling] Eliminando Auto Scaling Groups, Politicas y Launch Templates..." -ForegroundColor Yellow

$asgNames = @("asg-servia-backend")
foreach ($asg in $asgNames) {
    $asgCheck = aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names $asg --query "AutoScalingGroups[0].AutoScalingGroupName" --output text 2>$null
    if ($asgCheck -and $asgCheck -ne "None") {
        Write-Host "  -> Eliminando politicas de scaling para $asg..." -ForegroundColor Cyan
        $policies = aws autoscaling describe-policies --auto-scaling-group-name $asg --query "ScalingPolicies[*].PolicyName" --output text 2>$null
        foreach ($pol in ($policies -split '\s+' | Where-Object { $_ -ne "" })) {
            aws autoscaling delete-policy --auto-scaling-group-name $asg --policy-name $pol 2>$null | Out-Null
        }

        Write-Host "  -> Vaciando y eliminando Auto Scaling Group $asg..." -ForegroundColor Cyan
        aws autoscaling update-auto-scaling-group --auto-scaling-group-name $asg --min-size 0 --desired-capacity 0 2>$null | Out-Null
        aws autoscaling delete-auto-scaling-group --auto-scaling-group-name $asg --force-delete 2>$null | Out-Null
    }
}

Write-Host "  -> Eliminando Launch Templates..." -ForegroundColor Cyan
aws ec2 delete-launch-template --launch-template-name lt-servia-backend 2>$null | Out-Null

# Terminar cualquier instancia EC2 standalone residual
$InstanceIds = aws ec2 describe-instances `
  --filters "Name=tag:Name,Values=servia_backend_ec2,portal_data" "Name=instance-state-name,Values=running,stopped,pending" `
  --query "Reservations[*].Instances[*].InstanceId" `
  --output text 2>$null

if ($InstanceIds -and $InstanceIds.Trim() -ne "") {
    $idList = @($InstanceIds -split '\s+' | Where-Object { $_ -ne "" })
    Write-Host "  -> Terminando instancias EC2 residuales: $($idList -join ', ')..." -ForegroundColor Cyan
    aws ec2 terminate-instances --instance-ids $idList 2>$null | Out-Null
    aws ec2 wait instance-terminated --instance-ids $idList 2>$null
}

# =============================================================================
# FASE 3: ELIMINAR LOAD BALANCERS Y TARGET GROUPS
# =============================================================================
Write-Host ""
Write-Host "[Fase 3: Load Balancers] Eliminando ALBs y Target Groups..." -ForegroundColor Yellow
$Albs = @("alb-servia-api")
foreach ($albName in $Albs) {
    $albArn = aws elbv2 describe-load-balancers --names $albName --query "LoadBalancers[0].LoadBalancerArn" --output text 2>$null
    if ($albArn -and $albArn -ne "None" -and $albArn.Trim() -ne "") {
        Write-Host "  -> Eliminando ALB: $albName..." -ForegroundColor Cyan
        aws elbv2 delete-load-balancer --load-balancer-arn $albArn 2>$null | Out-Null
    }
}

Start-Sleep -Seconds 10

$Tgs = aws elbv2 describe-target-groups --query "TargetGroups[?starts_with(TargetGroupName, 'tg-servia') || starts_with(TargetGroupName, 'tg-ecs')].TargetGroupArn" --output text 2>$null
foreach ($tgArn in ($Tgs -split '\s+' | Where-Object { $_ -ne "" })) {
    Write-Host "  -> Eliminando Target Group: $tgArn..." -ForegroundColor Cyan
    aws elbv2 delete-target-group --target-group-arn $tgArn 2>$null | Out-Null
}

# =============================================================================
# FASE 4: ELIMINAR DISTRIBUCIONES DE CLOUDFRONT
# =============================================================================
Write-Host ""
Write-Host "[Fase 4: CloudFront] Verificando distribuciones CloudFront..." -ForegroundColor Yellow
$cfDists = aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='ServIA Frontend CloudFront CDN' || Comment=='Portal del Egresado - Frontend CloudFront CDN'].{Id:Id,ETag:ETag,Status:Status}" --output json 2>$null
if ($cfDists -and $cfDists -ne "null") {
    $distList = $cfDists | ConvertFrom-Json
    foreach ($d in $distList) {
        Write-Host "  -> Deshabilitando distribucion CloudFront $($d.Id)..." -ForegroundColor Cyan
        $cfg = aws cloudfront get-distribution-config --id $d.Id --output json 2>$null | ConvertFrom-Json
        $etag = aws cloudfront get-distribution-config --id $d.Id --query "ETag" --output text 2>$null
        $cfg.DistributionConfig.Enabled = $false
        $tmpCfg = "$PSScriptRoot\cf_disable_$($d.Id).json"
        $cfg.DistributionConfig | ConvertTo-Json -Depth 10 | Out-File $tmpCfg -Encoding ascii
        aws cloudfront update-distribution --id $d.Id --distribution-config file://$tmpCfg --if-match $etag 2>$null | Out-Null
        Remove-Item $tmpCfg -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "  -> No se encontraron distribuciones activas en CloudFront." -ForegroundColor Green
}

# =============================================================================
# FASE 5: VACIAR Y ELIMINAR BUCKETS S3
# =============================================================================
Write-Host ""
Write-Host "[Fase 5: S3 Storage] Vaciando y eliminando Buckets S3..." -ForegroundColor Yellow
$BucketsToDelete = @(
    "servia-front-$AccountId",
    "servia-deploy-$AccountId"
)

foreach ($b in $BucketsToDelete) {
    aws s3api head-bucket --bucket $b 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  -> Vaciando y eliminando bucket: $b..." -ForegroundColor Cyan
        aws s3 rb "s3://$b" --force 2>$null | Out-Null
        Write-Host "  -> Bucket eliminado: $b" -ForegroundColor Green
    }
}

# =============================================================================
# FASE 6: LIBERAR ELASTIC IPS
# =============================================================================
Release-ElasticIPs

# =============================================================================
# FASE 7: ESPERAR TERMINACIÓN DE RDS Y ELIMINAR DB SUBNET GROUPS
# =============================================================================
Write-Host ""
Write-Host "[Fase 7: RDS Cleanup] Esperando que finalice la eliminacion de RDS..." -ForegroundColor Yellow
foreach ($rdsId in $RdsInstances) {
    while ($true) {
        $st = aws rds describe-db-instances --db-instance-identifier $rdsId --query "DBInstances[0].DBInstanceStatus" --output text 2>$null
        if (-not $st -or $st -eq "None" -or $st.Trim() -eq "") { 
            Write-Host "  -> Instancia RDS $rdsId completamente eliminada." -ForegroundColor Green
            break 
        }
        Write-Host "  -> Esperando eliminacion de $rdsId (estado actual: $st)..." -ForegroundColor DarkYellow
        Start-Sleep -Seconds 15
    }
}

aws rds delete-db-subnet-group --db-subnet-group-name "servia-db-subnets" 2>$null | Out-Null

# =============================================================================
# FASE 8: ELIMINAR RECURSOS DE RED (SECURITY GROUPS, SUBNETS, ROUTE TABLES, IGW, VPC)
# =============================================================================
Write-Host ""
Write-Host "[Fase 8: Redes] Eliminando Security Groups, Subredes, Enrutamiento y VPC..." -ForegroundColor Yellow

$VpcNames = @("servia_vpc")
foreach ($vName in $VpcNames) {
    $vId = aws ec2 describe-vpcs --filters "Name=tag:Name,Values=$vName" --query "Vpcs[0].VpcId" --output text 2>$null
    if ($vId -and $vId -ne "None" -and $vId.Trim() -ne "") {
        Write-Host "Procesando eliminacion de VPC: $vName ($vId)..." -ForegroundColor Cyan

        # A. Eliminar NAT Gateways (si hubiese)
        $natGws = aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$vId" "Name=state,Values=available" --query "NatGateways[*].NatGatewayId" --output text 2>$null
        foreach ($ngw in ($natGws -split '\s+' | Where-Object { $_ -ne "" })) {
            Write-Host "  -> Eliminando NAT Gateway: $ngw..." -ForegroundColor Cyan
            aws ec2 delete-nat-gateway --nat-gateway-id $ngw 2>$null | Out-Null
        }

        # B. Eliminar Security Groups (excepto default)
        $sgs = aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$vId" --query "SecurityGroups[?GroupName!='default'].GroupId" --output text 2>$null
        foreach ($sg in ($sgs -split '\s+' | Where-Object { $_ -ne "" })) {
            aws ec2 revoke-security-group-ingress --group-id $sg --protocol all --source-group $sg 2>$null | Out-Null
            aws ec2 delete-security-group --group-id $sg 2>$null | Out-Null
        }

        # C. Desasociar y eliminar Internet Gateways
        $igws = aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$vId" --query "InternetGateways[*].InternetGatewayId" --output text 2>$null
        foreach ($igw in ($igws -split '\s+' | Where-Object { $_ -ne "" })) {
            Write-Host "  -> Desasociando y eliminando IGW: $igw..." -ForegroundColor Cyan
            aws ec2 detach-internet-gateway --internet-gateway-id $igw --vpc-id $vId 2>$null | Out-Null
            aws ec2 delete-internet-gateway --internet-gateway-id $igw 2>$null | Out-Null
        }

        # D. Eliminar Subredes
        $subnets = aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vId" --query "Subnets[*].SubnetId" --output text 2>$null
        foreach ($sub in ($subnets -split '\s+' | Where-Object { $_ -ne "" })) {
            Write-Host "  -> Eliminando Subred: $sub..." -ForegroundColor Cyan
            aws ec2 delete-subnet --subnet-id $sub 2>$null | Out-Null
        }

        # E. Eliminar Route Tables personalizadas
        $rts = aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$vId" --query "RouteTables[?Associations[0].Main!=``true``].RouteTableId" --output text 2>$null
        foreach ($rt in ($rts -split '\s+' | Where-Object { $_ -ne "" })) {
            Write-Host "  -> Eliminando Route Table: $rt..." -ForegroundColor Cyan
            aws ec2 delete-route-table --route-table-id $rt 2>$null | Out-Null
        }

        # F. Eliminar la VPC
        $retryVpc = 0
        while ($retryVpc -lt 5) {
            aws ec2 delete-vpc --vpc-id $vId 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  -> VPC $vName eliminada con exito." -ForegroundColor Green
                break
            }
            Start-Sleep -Seconds 5
            $retryVpc++
        }
    }
}

# =============================================================================
# FASE 9: LIMPIEZA DE ARCHIVOS LOCALES TEMPORALES
# =============================================================================
Write-Host ""
Write-Host "[Fase 9: Limpieza Local] Eliminando archivos temporales locales..." -ForegroundColor Yellow
$LocalTemps = @(
    "$PSScriptRoot\servia_ec2_key.pem",
    "$PSScriptRoot\portal_egresado_key.pem",
    "$PSScriptRoot\bucket_policy_front.json",
    "$PSScriptRoot\cf_config.json",
    "$PSScriptRoot\backend_bundle.zip",
    "$PSScriptRoot\asg_policy.json",
    "$PSScriptRoot\lt_data.json"
)
foreach ($f in $LocalTemps) {
    if (Test-Path $f) { Remove-Item $f -Force -ErrorAction SilentlyContinue }
}

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host " DESTRUCCION FINALIZADA! Todos los recursos liberados." -ForegroundColor Green -BackgroundColor Black
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""
