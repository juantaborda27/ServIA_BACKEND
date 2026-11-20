param(
    # Además de los recursos ECS, elimina el RDS compartido, su subnet group y la VPC servia_vpc
    [switch]$Completo
)

$ErrorActionPreference = "Continue"

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host " Iniciando Destruccion Cloud ServIA (Amazon ECS)       " -ForegroundColor Cyan -BackgroundColor DarkRed
if ($Completo) {
    Write-Host " Modo: COMPLETO (ECS + RDS + VPC)                      " -ForegroundColor White
} else {
    Write-Host " Modo: solo recursos ECS (RDS y VPC se conservan)      " -ForegroundColor White
}
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

$Ec2Test = aws ec2 describe-vpcs --max-items 1 2>&1
if ($LASTEXITCODE -ne 0 -or $Ec2Test -match "voc-cancel-cred" -or $Ec2Test -match "UnauthorizedOperation") {
    Write-Host ""
    Write-Host "=======================================================" -ForegroundColor Red
    Write-Host "[ERROR] Tu sesion de AWS Learner Lab ha expirado o esta detenida." -ForegroundColor Red
    Write-Host "=======================================================" -ForegroundColor Red
    Write-Host "Por favor actualiza credentials.ps1 con credenciales nuevas." -ForegroundColor Yellow
    exit 1
}

$AccountId = (aws sts get-caller-identity --query Account --output text 2>$null).Trim()
Write-Host "AWS Account ID: $AccountId" -ForegroundColor Cyan

# Mismos nombres que deploy_ecs.ps1
$ClusterName  = "servia-ecs-cluster"
$Services     = @("servia-backend-service", "servia-frontend-service")
$TaskFamilies = @("servia-backend", "servia-frontend", "servia-db-init")
$Repos        = @("servia-backend", "servia-frontend")
$AlbName      = "alb-servia-ecs"
$TgNames      = @("tg-servia-ecs-back", "tg-servia-ecs-front")
$LogGroups    = @("/ecs/servia-backend", "/ecs/servia-frontend", "/ecs/servia-db-init")
$Secrets      = @("servia/database-url", "servia/db-password", "servia/jwt-secret")
$SgNames      = @("sg_servia_ecs_alb", "sg_servia_ecs_back", "sg_servia_ecs_front")
$SubnetNames  = @("servia_sub_ecs_a", "servia_sub_ecs_b")
$Alarms       = @(
    "servia-ecs-backend-cpu-alta",
    "servia-ecs-backend-memoria-alta",
    "servia-ecs-alb-errores-5xx",
    "servia-ecs-backend-hosts-bajos",
    "servia-ecs-frontend-hosts-bajos",
    "servia-ecs-rds-cpu-alta"
)

$VpcId = aws ec2 describe-vpcs --filters "Name=tag:Name,Values=servia_vpc" --query "Vpcs[0].VpcId" --output text 2>$null
if ($VpcId) { $VpcId = $VpcId.Trim() }
$HasVpc = ($VpcId -and $VpcId -ne "None")

# =============================================================================
# FASE 1: SOLICITAR ELIMINACIÓN ASÍNCRONA DE RDS (SOLO EN MODO -Completo)
# =============================================================================
if ($Completo) {
    Write-Host ""
    Write-Host "[Fase 1: RDS] Solicitando eliminacion de servia-db-rds (en segundo plano)..." -ForegroundColor Yellow
    $RdsStatus = aws rds describe-db-instances --db-instance-identifier servia-db-rds --query "DBInstances[0].DBInstanceStatus" --output text 2>$null
    if ($RdsStatus -and $RdsStatus -ne "None" -and $RdsStatus.Trim() -ne "") {
        if ($RdsStatus.Trim() -ne "deleting") {
            aws rds delete-db-instance --db-instance-identifier servia-db-rds --skip-final-snapshot --delete-automated-backups 2>$null | Out-Null
            Write-Host "  -> delete-db-instance solicitado (sin snapshot final)." -ForegroundColor Cyan
        } else {
            Write-Host "  -> servia-db-rds ya se encuentra en proceso de eliminacion." -ForegroundColor DarkGray
        }
    } else {
        Write-Host "  -> No existe instancia RDS servia-db-rds." -ForegroundColor DarkGray
    }
}

# =============================================================================
# FASE 2: AUTO SCALING Y SERVICIOS ECS
# =============================================================================
Write-Host ""
Write-Host "[Fase 2: Servicios ECS] Desactivando auto scaling y eliminando servicios..." -ForegroundColor Yellow

foreach ($svc in $Services) {
    # Primero el auto scaling, para que no vuelva a subir el minimo de tareas
    $resId = "service/$ClusterName/$svc"
    aws application-autoscaling delete-scaling-policy --service-namespace ecs --resource-id $resId --scalable-dimension ecs:service:DesiredCount --policy-name "$svc-cpu70" 2>$null | Out-Null
    aws application-autoscaling deregister-scalable-target --service-namespace ecs --resource-id $resId --scalable-dimension ecs:service:DesiredCount 2>$null | Out-Null

    $status = aws ecs describe-services --cluster $ClusterName --services $svc --query "services[0].status" --output text 2>$null
    if ($status -eq "ACTIVE" -or $status -eq "DRAINING") {
        Write-Host "  -> Escalando a 0 y eliminando servicio: $svc..." -ForegroundColor Cyan
        aws ecs update-service --cluster $ClusterName --service $svc --desired-count 0 2>$null | Out-Null
        aws ecs delete-service --cluster $ClusterName --service $svc --force 2>$null | Out-Null
    } else {
        Write-Host "  -> Servicio no encontrado: $svc" -ForegroundColor DarkGray
    }
}

Write-Host "  -> Esperando a que los servicios queden inactivos..." -ForegroundColor DarkYellow
aws ecs wait services-inactive --cluster $ClusterName --services $Services 2>$null

# Detener cualquier tarea suelta (p. ej. la tarea de inicializacion de BD)
$RunningTasks = aws ecs list-tasks --cluster $ClusterName --query "taskArns" --output text 2>$null
$taskList = @($RunningTasks -split '\s+' | Where-Object { $_ -match '^arn:' })
if ($taskList.Count -gt 0) {
    foreach ($t in $taskList) {
        aws ecs stop-task --cluster $ClusterName --task $t --reason "destroy_ecs.ps1" 2>$null | Out-Null
    }
    Write-Host "  -> Deteniendo $($taskList.Count) tarea(s) residual(es)..." -ForegroundColor Cyan
    aws ecs wait tasks-stopped --cluster $ClusterName --tasks $taskList 2>$null
}
Write-Host "  -> Servicios y tareas ECS eliminados." -ForegroundColor Green

# =============================================================================
# FASE 3: TASK DEFINITIONS Y CLUSTER
# =============================================================================
Write-Host ""
Write-Host "[Fase 3: Cluster ECS] Desregistrando task definitions y eliminando cluster..." -ForegroundColor Yellow

foreach ($fam in $TaskFamilies) {
    $tds = aws ecs list-task-definitions --family-prefix $fam --status ACTIVE --query "taskDefinitionArns" --output text 2>$null
    $tdList = @($tds -split '\s+' | Where-Object { $_ -match '^arn:' })
    foreach ($td in $tdList) {
        aws ecs deregister-task-definition --task-definition $td 2>$null | Out-Null
    }
    if ($tdList.Count -gt 0) {
        Write-Host "  -> $fam : $($tdList.Count) revision(es) desregistrada(s)" -ForegroundColor Green
    }
}

$ClusterStatus = aws ecs describe-clusters --clusters $ClusterName --query "clusters[0].status" --output text 2>$null
if ($ClusterStatus -eq "ACTIVE") {
    aws ecs delete-cluster --cluster $ClusterName 2>$null | Out-Null
    Write-Host "  -> Cluster eliminado: $ClusterName" -ForegroundColor Green
} else {
    Write-Host "  -> Cluster no encontrado: $ClusterName" -ForegroundColor DarkGray
}

# =============================================================================
# FASE 4: LOAD BALANCER Y TARGET GROUPS
# =============================================================================
Write-Host ""
Write-Host "[Fase 4: Load Balancer] Eliminando ALB y Target Groups..." -ForegroundColor Yellow

$AlbArn = aws elbv2 describe-load-balancers --names $AlbName --query "LoadBalancers[0].LoadBalancerArn" --output text 2>$null
if ($AlbArn -and $AlbArn -ne "None" -and $AlbArn.Trim() -ne "") {
    aws elbv2 delete-load-balancer --load-balancer-arn $AlbArn 2>$null | Out-Null
    Write-Host "  -> Eliminando ALB $AlbName (esperando confirmacion)..." -ForegroundColor Cyan
    aws elbv2 wait load-balancers-deleted --load-balancer-arns $AlbArn 2>$null
    Write-Host "  -> ALB eliminado." -ForegroundColor Green
} else {
    Write-Host "  -> ALB no encontrado: $AlbName" -ForegroundColor DarkGray
}

foreach ($tgName in $TgNames) {
    $tgArn = aws elbv2 describe-target-groups --names $tgName --query "TargetGroups[0].TargetGroupArn" --output text 2>$null
    if ($tgArn -and $tgArn -ne "None" -and $tgArn.Trim() -ne "") {
        $ok = $false
        for ($r = 0; $r -lt 6 -and -not $ok; $r++) {
            aws elbv2 delete-target-group --target-group-arn $tgArn 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { $ok = $true } else { Start-Sleep -Seconds 5 }
        }
        if ($ok) { Write-Host "  -> Target Group eliminado: $tgName" -ForegroundColor Green }
        else { Write-Host "  -> [AVISO] No se pudo eliminar el Target Group $tgName" -ForegroundColor DarkYellow }
    }
}

# =============================================================================
# FASE 5: ECR, SECRETS MANAGER, LOGS Y ALARMAS
# =============================================================================
Write-Host ""
Write-Host "[Fase 5: Servicios gestionados] Eliminando ECR, secretos, logs y alarmas..." -ForegroundColor Yellow

foreach ($repo in $Repos) {
    aws ecr delete-repository --repository-name $repo --force 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host "  -> Repositorio ECR eliminado (con imagenes): $repo" -ForegroundColor Green }
}

# Sin periodo de recuperacion, para que un nuevo deploy pueda recrearlos de inmediato
foreach ($s in $Secrets) {
    aws secretsmanager delete-secret --secret-id $s --force-delete-without-recovery 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host "  -> Secreto eliminado: $s" -ForegroundColor Green }
}

foreach ($lg in $LogGroups) {
    aws logs delete-log-group --log-group-name $lg 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host "  -> Log group eliminado: $lg" -ForegroundColor Green }
}

aws cloudwatch delete-alarms --alarm-names $Alarms 2>$null | Out-Null
Write-Host "  -> Alarmas CloudWatch eliminadas." -ForegroundColor Green

$SnsTopicArn = aws sns list-topics --query "Topics[?ends_with(TopicArn,'servia-alertas-ecs')].TopicArn | [0]" --output text 2>$null
if ($SnsTopicArn -and $SnsTopicArn -ne "None" -and $SnsTopicArn.Trim() -ne "") {
    aws sns delete-topic --topic-arn $SnsTopicArn 2>$null | Out-Null
    Write-Host "  -> SNS Topic 'servia-alertas-ecs' eliminado." -ForegroundColor Green
}

# =============================================================================
# FASE 6: NAT GATEWAY Y SU IP ELASTICA
# =============================================================================
Write-Host ""
Write-Host "[Fase 6: NAT Gateway] Eliminando NAT Gateway y liberando su IP Elastica..." -ForegroundColor Yellow

if ($HasVpc) {
    $NatJson = aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$VpcId" "Name=tag:Name,Values=servia_nat_ecs" "Name=state,Values=pending,available" --query "NatGateways[*].{Id:NatGatewayId,Alloc:NatGatewayAddresses[0].AllocationId}" --output json 2>$null
    $Nats = @()
    if ($NatJson) { $Nats = @($NatJson | ConvertFrom-Json) }
    if ($Nats.Count -gt 0) {
        foreach ($n in $Nats) {
            Write-Host "  -> Eliminando NAT Gateway $($n.Id) (tarda 1-2 minutos)..." -ForegroundColor Cyan
            aws ec2 delete-nat-gateway --nat-gateway-id $n.Id 2>$null | Out-Null
        }
        aws ec2 wait nat-gateway-deleted --nat-gateway-ids ($Nats | ForEach-Object { $_.Id }) 2>$null
        foreach ($n in $Nats) {
            if ($n.Alloc) {
                aws ec2 release-address --allocation-id $n.Alloc 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) { Write-Host "  -> IP Elastica liberada: $($n.Alloc)" -ForegroundColor Green }
            }
        }
        Write-Host "  -> NAT Gateway eliminado." -ForegroundColor Green
    } else {
        Write-Host "  -> No hay NAT Gateway servia_nat_ecs activo." -ForegroundColor DarkGray
    }

    # EIP etiquetada que haya quedado huérfana (p. ej. deploy interrumpido)
    $OrphanEips = aws ec2 describe-addresses --filters "Name=tag:Name,Values=servia_nat_ecs_eip" --query "Addresses[?AssociationId==null].AllocationId" --output text 2>$null
    foreach ($e in ($OrphanEips -split '\s+' | Where-Object { $_ -match '^eipalloc-' })) {
        aws ec2 release-address --allocation-id $e 2>$null | Out-Null
        Write-Host "  -> IP Elastica huerfana liberada: $e" -ForegroundColor Green
    }
}

# =============================================================================
# FASE 7: RED ECS (SECURITY GROUPS, SUBREDES PRIVADAS Y TABLA DE RUTAS)
# =============================================================================
Write-Host ""
Write-Host "[Fase 7: Red ECS] Eliminando security groups, subredes privadas y tabla de rutas ECS..." -ForegroundColor Yellow

if ($HasVpc) {
    $SgIds = @{}
    foreach ($sgName in $SgNames) {
        $id = aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VpcId" "Name=group-name,Values=$sgName" --query "SecurityGroups[0].GroupId" --output text 2>$null
        if ($id -and $id -ne "None") { $SgIds[$sgName] = $id.Trim() }
    }

    # Quitar las reglas que referencian a otros SG (RDS <- backend, backend/frontend <- ALB)
    $SgRds = aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VpcId" "Name=group-name,Values=sg_servia_rds" --query "SecurityGroups[0].GroupId" --output text 2>$null
    if ($SgRds -and $SgRds -ne "None" -and $SgIds.ContainsKey("sg_servia_ecs_back")) {
        aws ec2 revoke-security-group-ingress --group-id $SgRds --protocol tcp --port 5432 --source-group $SgIds["sg_servia_ecs_back"] 2>$null | Out-Null
    }
    if ($SgIds.ContainsKey("sg_servia_ecs_alb")) {
        if ($SgIds.ContainsKey("sg_servia_ecs_back")) {
            aws ec2 revoke-security-group-ingress --group-id $SgIds["sg_servia_ecs_back"] --protocol tcp --port 8000 --source-group $SgIds["sg_servia_ecs_alb"] 2>$null | Out-Null
        }
        if ($SgIds.ContainsKey("sg_servia_ecs_front")) {
            aws ec2 revoke-security-group-ingress --group-id $SgIds["sg_servia_ecs_front"] --protocol tcp --port 80 --source-group $SgIds["sg_servia_ecs_alb"] 2>$null | Out-Null
        }
    }

    # Las interfaces de red (ENI) de Fargate y del ALB tardan en liberarse: se reintenta
    foreach ($sgName in @("sg_servia_ecs_back", "sg_servia_ecs_front", "sg_servia_ecs_alb")) {
        if (-not $SgIds.ContainsKey($sgName)) { continue }
        $ok = $false
        for ($r = 0; $r -lt 12 -and -not $ok; $r++) {
            aws ec2 delete-security-group --group-id $SgIds[$sgName] 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { $ok = $true } else { Start-Sleep -Seconds 10 }
        }
        if ($ok) { Write-Host "  -> Security Group eliminado: $sgName" -ForegroundColor Green }
        else { Write-Host "  -> [AVISO] $sgName sigue en uso (ENI pendiente). Vuelve a ejecutar el script en unos minutos." -ForegroundColor DarkYellow }
    }

    foreach ($subName in $SubnetNames) {
        $subId = aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VpcId" "Name=tag:Name,Values=$subName" --query "Subnets[0].SubnetId" --output text 2>$null
        if (-not $subId -or $subId -eq "None") { continue }
        $ok = $false
        for ($r = 0; $r -lt 12 -and -not $ok; $r++) {
            aws ec2 delete-subnet --subnet-id $subId 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { $ok = $true } else { Start-Sleep -Seconds 10 }
        }
        if ($ok) { Write-Host "  -> Subred eliminada: $subName ($subId)" -ForegroundColor Green }
        else { Write-Host "  -> [AVISO] No se pudo eliminar la subred $subName (ENI pendiente)." -ForegroundColor DarkYellow }
    }

    $RtEcs = aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VpcId" "Name=tag:Name,Values=servia_rt_ecs_priv" --query "RouteTables[0].RouteTableId" --output text 2>$null
    if ($RtEcs -and $RtEcs -ne "None") {
        $assocs = aws ec2 describe-route-tables --route-table-ids $RtEcs --query "RouteTables[0].Associations[?Main!=``true``].RouteTableAssociationId" --output text 2>$null
        foreach ($a in ($assocs -split '\s+' | Where-Object { $_ -match '^rtbassoc-' })) {
            aws ec2 disassociate-route-table --association-id $a 2>$null | Out-Null
        }
        aws ec2 delete-route-table --route-table-id $RtEcs 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Host "  -> Tabla de rutas eliminada: servia_rt_ecs_priv" -ForegroundColor Green }
    }
} else {
    Write-Host "  -> VPC servia_vpc no encontrada; nada que limpiar en red." -ForegroundColor DarkGray
}

# =============================================================================
# FASE 8: RDS, SUBNET GROUP Y VPC (SOLO EN MODO -Completo)
# =============================================================================
if ($Completo) {
    Write-Host ""
    Write-Host "[Fase 8: RDS y VPC] Esperando eliminacion de RDS y limpiando la VPC compartida..." -ForegroundColor Yellow

    while ($true) {
        $st = aws rds describe-db-instances --db-instance-identifier servia-db-rds --query "DBInstances[0].DBInstanceStatus" --output text 2>$null
        if (-not $st -or $st -eq "None" -or $st.Trim() -eq "") {
            Write-Host "  -> Instancia RDS servia-db-rds eliminada." -ForegroundColor Green
            break
        }
        Write-Host "  -> Esperando eliminacion de servia-db-rds (estado: $st)..." -ForegroundColor DarkYellow
        Start-Sleep -Seconds 20
    }
    aws rds delete-db-subnet-group --db-subnet-group-name "servia-db-subnets" 2>$null | Out-Null

    # Si el despliegue EC2 (deploy_s3.ps1) sigue activo, la VPC se conserva
    $AsgS3 = aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names asg-servia-backend --query "AutoScalingGroups[0].AutoScalingGroupName" --output text 2>$null
    if ($AsgS3 -and $AsgS3 -ne "None") {
        Write-Host "  -> [AVISO] El despliegue EC2 (asg-servia-backend) sigue activo: se conserva la VPC." -ForegroundColor DarkYellow
        Write-Host "     Usa destroy_s3.ps1 para eliminar ese despliegue y la VPC." -ForegroundColor DarkYellow
    } elseif ($HasVpc) {
        Write-Host "Procesando eliminacion de VPC servia_vpc ($VpcId)..." -ForegroundColor Cyan

        $sgs = aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VpcId" --query "SecurityGroups[?GroupName!='default'].GroupId" --output text 2>$null
        $sgList = @($sgs -split '\s+' | Where-Object { $_ -match '^sg-' })
        # Quitar todas las reglas de ingreso primero (evita dependencias cruzadas entre SG)
        foreach ($sg in $sgList) {
            $perms = aws ec2 describe-security-groups --group-ids $sg --query "SecurityGroups[0].IpPermissions" --output json 2>$null
            if ($perms -and $perms.Trim() -ne "[]") {
                $permFile = Join-Path $env:TEMP "servia_perm_$sg.json"
                [IO.File]::WriteAllText($permFile, ($perms -join "`n"), (New-Object Text.UTF8Encoding $false))
                aws ec2 revoke-security-group-ingress --group-id $sg --ip-permissions "file://$permFile" 2>$null | Out-Null
                Remove-Item $permFile -ErrorAction SilentlyContinue
            }
        }
        foreach ($sg in $sgList) {
            aws ec2 delete-security-group --group-id $sg 2>$null | Out-Null
        }

        $igws = aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VpcId" --query "InternetGateways[*].InternetGatewayId" --output text 2>$null
        foreach ($igw in ($igws -split '\s+' | Where-Object { $_ -ne "" })) {
            aws ec2 detach-internet-gateway --internet-gateway-id $igw --vpc-id $VpcId 2>$null | Out-Null
            aws ec2 delete-internet-gateway --internet-gateway-id $igw 2>$null | Out-Null
            Write-Host "  -> IGW eliminado: $igw" -ForegroundColor Green
        }

        $subnets = aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VpcId" --query "Subnets[*].SubnetId" --output text 2>$null
        foreach ($sub in ($subnets -split '\s+' | Where-Object { $_ -ne "" })) {
            aws ec2 delete-subnet --subnet-id $sub 2>$null | Out-Null
            Write-Host "  -> Subred eliminada: $sub" -ForegroundColor Green
        }

        $rts = aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VpcId" --query "RouteTables[?Associations[0].Main!=``true``].RouteTableId" --output text 2>$null
        foreach ($rt in ($rts -split '\s+' | Where-Object { $_ -ne "" })) {
            aws ec2 delete-route-table --route-table-id $rt 2>$null | Out-Null
        }

        $retryVpc = 0
        while ($retryVpc -lt 6) {
            aws ec2 delete-vpc --vpc-id $VpcId 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  -> VPC servia_vpc eliminada con exito." -ForegroundColor Green
                break
            }
            Start-Sleep -Seconds 10
            $retryVpc++
        }
        if ($retryVpc -ge 6) {
            Write-Host "  -> [AVISO] No se pudo eliminar la VPC (dependencias pendientes). Reintenta en unos minutos." -ForegroundColor DarkYellow
        }
    }
}

# =============================================================================
# FASE 9: LIMPIEZA DE ARCHIVOS LOCALES TEMPORALES
# =============================================================================
Write-Host ""
Write-Host "[Fase 9: Limpieza Local] Eliminando archivos temporales locales..." -ForegroundColor Yellow
$TmpDir = Join-Path $env:TEMP "servia-ecs-deploy"
if (Test-Path $TmpDir) { Remove-Item $TmpDir -Recurse -Force -ErrorAction SilentlyContinue }
$Registry = "$AccountId.dkr.ecr.us-east-1.amazonaws.com"
docker logout $Registry 2>$null | Out-Null

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host " DESTRUCCION ECS FINALIZADA!                           " -ForegroundColor Green -BackgroundColor Black
Write-Host "=======================================================" -ForegroundColor Cyan
if (-not $Completo) {
    Write-Host "Se conservaron: RDS servia-db-rds y VPC servia_vpc (compartidos con deploy_s3.ps1)." -ForegroundColor DarkYellow
    Write-Host "  -> El RDS sigue cobrando por hora. Para eliminarlo tambien ejecuta:" -ForegroundColor DarkYellow
    Write-Host "     .\destroy_ecs.ps1 -Completo" -ForegroundColor White
}
Write-Host ""
