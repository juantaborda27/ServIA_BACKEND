-- =============================================================================
-- ServIA Database Schema & Seed Data (PostgreSQL)
-- Compatible con Amazon RDS PostgreSQL y Docker Compose
-- =============================================================================

-- Habilitar extensión para generación de UUIDs si no existe
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- 1. TIPOS ENUM PERSONALIZADOS (Idempotentes)
-- =============================================================================
DO $$ BEGIN
    CREATE TYPE estado_postulacion AS ENUM ('pendiente', 'aceptada', 'rechazada', 'en_espera');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE nivel_urgencia AS ENUM ('ahora', 'hoy', 'esta semana', 'no tengo prisa');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE estado_publicacion AS ENUM ('activo', 'acuerdo', 'en_progreso', 'terminado', 'cancelado', 'expirado');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- =============================================================================
-- 2. TABLAS DE LA APLICACIÓN
-- =============================================================================

-- 2.1 Usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    nombre_completo TEXT NOT NULL,
    telefono TEXT,
    foto_perfil TEXT,
    ubicacion TEXT,
    fecha_registro TIMESTAMPTZ DEFAULT now() NOT NULL,
    activo BOOLEAN DEFAULT TRUE NOT NULL
);

-- 2.2 Clientes (Relación 1:1 con Usuarios)
CREATE TABLE IF NOT EXISTS clientes (
    id UUID PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_creacion TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- 2.3 Prestadores (Relación 1:1 con Usuarios)
CREATE TABLE IF NOT EXISTS prestadores (
    id UUID PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    descripcion TEXT,
    disponible BOOLEAN DEFAULT TRUE NOT NULL,
    verificado BOOLEAN DEFAULT FALSE NOT NULL,
    fecha_creacion TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- 2.4 Categorías de Servicios
CREATE TABLE IF NOT EXISTS categorias (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre TEXT NOT NULL,
    descripcion TEXT,
    icono TEXT
);

-- 2.5 Especialidades (M:N entre Prestador y Categoría)
CREATE TABLE IF NOT EXISTS especialidades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prestador_id UUID NOT NULL REFERENCES prestadores(id) ON DELETE CASCADE,
    categoria_id UUID NOT NULL REFERENCES categorias(id) ON DELETE CASCADE,
    fecha_creacion TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT especialidades_unique UNIQUE (prestador_id, categoria_id)
);

-- 2.6 Catálogo de Servicios Ofrecidos por Prestadores
CREATE TABLE IF NOT EXISTS servicios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prestador_id UUID NOT NULL REFERENCES prestadores(id) ON DELETE CASCADE,
    categoria_id UUID NOT NULL REFERENCES categorias(id) ON DELETE RESTRICT,
    nombre TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    precio_desde NUMERIC(10, 2) NOT NULL,
    precio_hasta NUMERIC(10, 2) NOT NULL,
    duracion_estimada INTEGER NOT NULL,
    activo BOOLEAN DEFAULT FALSE,
    fecha_publicacion TIMESTAMPTZ,
    fecha_creacion TIMESTAMPTZ DEFAULT now()
);

-- 2.7 Publicaciones de Solicitudes de Clientes
CREATE TABLE IF NOT EXISTS publicaciones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    descripcion TEXT NOT NULL,
    categoria_id UUID NOT NULL REFERENCES categorias(id),
    urgencia nivel_urgencia NOT NULL,
    usuario_id UUID NOT NULL REFERENCES usuarios(id),
    estado estado_publicacion NOT NULL DEFAULT 'activo',
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- 2.8 Postulaciones de Prestadores a Publicaciones
CREATE TABLE IF NOT EXISTS postulaciones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    publicacion_id UUID NOT NULL REFERENCES publicaciones(id) ON DELETE CASCADE,
    prestador_id UUID NOT NULL REFERENCES prestadores(id) ON DELETE CASCADE,
    precio_ofertado NUMERIC(10, 2) NOT NULL CHECK (precio_ofertado > 0),
    disponibilidad VARCHAR(100) NOT NULL,
    mensaje TEXT NOT NULL,
    estado estado_postulacion NOT NULL DEFAULT 'pendiente',
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_prestador_solicitud UNIQUE (publicacion_id, prestador_id)
);

-- =============================================================================
-- 3. TRIGGERS PARA ACTUALIZACIÓN AUTOMÁTICA DE updated_at
-- =============================================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_postulaciones_updated_at ON postulaciones;
CREATE TRIGGER trg_postulaciones_updated_at
BEFORE UPDATE ON postulaciones
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_publicaciones_updated_at ON publicaciones;
CREATE TRIGGER trg_publicaciones_updated_at
BEFORE UPDATE ON publicaciones
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 4. SEMILLAS (SEED DATA): CATEGORÍAS DEL FRONTEND CON SUS UUIDS EXACTOS
-- =============================================================================
INSERT INTO categorias (id, nombre, icono) VALUES
('b42848e1-c8fd-4ab7-9cc0-21d25f360bda', 'Limpieza', 'sparkles-outline'),
('25c52bf4-f66b-4f83-bae9-365075e8546a', 'Albañilería', 'hammer-outline'),
('79ff9223-a11e-448a-b383-88e947de7efe', 'Pintura', 'color-palette-outline'),
('8866df0e-386c-4130-bec1-a5535573a181', 'Climatización', 'thermometer-outline'),
('309b7658-ec49-4ed9-8e1d-babef448ae87', 'Plomería', 'water-outline'),
('6cdb3be6-7f4b-48d5-8ccb-bcde129a86ed', 'Electricidad', 'flash-outline'),
('092c10e9-3f3e-430b-bffa-a493f00be823', 'Carpintería', 'construct-outline'),
('327708fe-3d6a-40dd-a95b-a3010ac9de0d', 'Cerrajería', 'key-outline'),
('395845b8-332e-4f95-b686-d6e824a62a78', 'Jardinería', 'leaf-outline'),
('a38e04db-de6c-46d1-9639-6e99110b94df', 'Limpieza del hogar', 'home-outline'),
('43ccdfae-2bbb-4904-9824-b326e9e966b1', 'Techos e impermeabilización', 'rainy-outline'),
('75597730-d042-4b18-979f-9a5205dde131', 'Drywall y cielo raso', 'layers-outline'),
('8ebe6587-f1f5-4fa8-8ad6-43ba21714d7b', 'Aire acondicionado', 'snow-outline'),
('f1d3e8cb-6c54-481e-aacc-afa5fd1b88db', 'Refrigeración', 'snow-outline'),
('6017401d-bdd3-4a8e-8834-749e9545c856', 'Gasfitería', 'build-outline'),
('6f5ecc04-d60b-481e-9bef-f9f022f75717', 'Instalación de pisos', 'grid-outline'),
('b94591be-b28d-42c4-9ad2-9fcd22307e94', 'Vidriería y aluminio', 'cube-outline'),
('c8495666-2db2-4981-a508-fe2671e5b189', 'Control de plagas', 'bug-outline'),
('bc7ee3e3-5815-4dbf-93ca-ec510ae1767e', 'Mudanzas', 'archive-outline'),
('867ce311-05ed-48fe-bcfe-67bd0b28e6d3', 'Remodelación', 'business-outline'),
('717c493a-ca8b-4f88-b451-0d89232cf5d2', 'Decoración de interiores', 'color-wand-outline'),
('c3fd927e-28a2-43aa-91b6-3a7beca24245', 'Soldadura y estructuras metálicas', 'flame-outline'),
('9e161b76-b6ea-44a4-99e2-aebdf215d93d', 'Impermeabilización de tanques', 'shield-checkmark-outline'),
('9c2f2df7-72e1-48e2-b0bd-d40b84429ba3', 'Automatización del hogar', 'hardware-chip-outline'),
('8936202d-d9f8-4774-bdae-eca37db04a04', 'Piscinas', 'water-outline'),
('17d871cf-6507-4149-8206-7f6e8e57be40', 'Electrodomésticos', 'tv-outline'),
('b5e66ffa-abfe-4098-920b-ee9490c26667', 'Mecánica automotriz a domicilio', 'car-outline')
ON CONFLICT (id) DO NOTHING;

