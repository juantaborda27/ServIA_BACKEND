from typing import Optional
import datetime
import decimal
import enum
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKeyConstraint, Index, Integer, Numeric, PrimaryKeyConstraint, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class EstadoPostulacion(str, enum.Enum):
    PENDIENTE = 'pendiente'
    ACEPTADA = 'aceptada'
    RECHAZADA = 'rechazada'
    EN_ESPERA = 'en_espera'


class EstadoPublicacion(str, enum.Enum):
    ACTIVO = 'activo'
    ACUERDO = 'acuerdo'
    EN_PROGRESO = 'en_progreso'
    TERMINADO = 'terminado'
    CANCELADO = 'cancelado'
    EXPIRADO = 'expirado'


class NivelUrgencia(str, enum.Enum):
    AHORA = 'ahora'
    HOY = 'hoy'
    ESTA_SEMANA = 'esta semana'
    NO_TENGO_PRISA = 'no tengo prisa'


class Categorias(Base):
    __tablename__ = 'categorias'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='categorias_pkey'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    icono: Mapped[Optional[str]] = mapped_column(Text)

    publicaciones: Mapped[list['Publicaciones']] = relationship('Publicaciones', back_populates='categoria')
    especialidades: Mapped[list['Especialidades']] = relationship('Especialidades', back_populates='categoria')
    servicios: Mapped[list['Servicios']] = relationship('Servicios', back_populates='categoria')


class Usuarios(Base):
    __tablename__ = 'usuarios'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='usuarios_pkey'),
        UniqueConstraint('email', name='usuarios_email_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_registro: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    hashed_password: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'$2b$12$Q0bsuD6C1MUpbKIC1Gtd0evarR35asVs3qjH5imhg5UgIigqaOI2i'::character varying"))
    telefono: Mapped[Optional[str]] = mapped_column(Text)
    foto_perfil: Mapped[Optional[str]] = mapped_column(Text)
    ubicacion: Mapped[Optional[str]] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(Text)

    publicaciones: Mapped[list['Publicaciones']] = relationship('Publicaciones', back_populates='usuario')
    mensajes_id_destinatario: Mapped[list['Mensajes']] = relationship('Mensajes', foreign_keys='[Mensajes.id_destinatario]', back_populates='usuarios')
    mensajes_id_remitente: Mapped[list['Mensajes']] = relationship('Mensajes', foreign_keys='[Mensajes.id_remitente]', back_populates='usuarios_')


class Clientes(Usuarios):
    __tablename__ = 'clientes'
    __table_args__ = (
        ForeignKeyConstraint(['id'], ['usuarios.id'], ondelete='CASCADE', name='clientes_id_fkey'),
        PrimaryKeyConstraint('id', name='clientes_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))


class Prestadores(Usuarios):
    __tablename__ = 'prestadores'
    __table_args__ = (
        ForeignKeyConstraint(['id'], ['usuarios.id'], ondelete='CASCADE', name='prestadores_id_fkey'),
        PrimaryKeyConstraint('id', name='prestadores_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    disponible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    verificado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    descripcion: Mapped[Optional[str]] = mapped_column(Text)

    especialidades: Mapped[list['Especialidades']] = relationship('Especialidades', back_populates='prestador')
    postulaciones: Mapped[list['Postulaciones']] = relationship('Postulaciones', back_populates='prestador')
    servicios: Mapped[list['Servicios']] = relationship('Servicios', back_populates='prestador')


class Publicaciones(Base):
    __tablename__ = 'publicaciones'
    __table_args__ = (
        ForeignKeyConstraint(['categoria_id'], ['categorias.id'], name='publicaciones_categoria_id_fkey'),
        ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name='publicaciones_usuario_id_fkey'),
        PrimaryKeyConstraint('id', name='publicaciones_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    categoria_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    urgencia: Mapped[NivelUrgencia] = mapped_column(Enum(NivelUrgencia, values_callable=lambda cls: [member.value for member in cls], name='nivel_urgencia'), nullable=False)
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, server_default=text('auth.uid()'))
    estado: Mapped[EstadoPublicacion] = mapped_column(Enum(EstadoPublicacion, values_callable=lambda cls: [member.value for member in cls], name='estado_publicacion'), nullable=False, server_default=text("'activo'::estado_publicacion"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))

    categoria: Mapped['Categorias'] = relationship('Categorias', back_populates='publicaciones')
    usuario: Mapped['Usuarios'] = relationship('Usuarios', back_populates='publicaciones')


class Especialidades(Base):
    __tablename__ = 'especialidades'
    __table_args__ = (
        ForeignKeyConstraint(['categoria_id'], ['categorias.id'], ondelete='CASCADE', name='especialidades_categoria_id_fkey'),
        ForeignKeyConstraint(['prestador_id'], ['prestadores.id'], ondelete='CASCADE', name='especialidades_prestador_id_fkey'),
        PrimaryKeyConstraint('id', name='especialidades_pkey'),
        UniqueConstraint('prestador_id', 'categoria_id', name='especialidades_unique')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    prestador_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    categoria_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))

    categoria: Mapped['Categorias'] = relationship('Categorias', back_populates='especialidades')
    prestador: Mapped['Prestadores'] = relationship('Prestadores', back_populates='especialidades')


class Postulaciones(Base):
    __tablename__ = 'postulaciones'
    __table_args__ = (
        CheckConstraint('precio_ofertado > 0::numeric', name='postulaciones_precio_ofertado_check'),
        ForeignKeyConstraint(['prestador_id'], ['prestadores.id'], ondelete='CASCADE', name='postulaciones_prestador_id_fkey'),
        PrimaryKeyConstraint('id', name='postulaciones_pkey'),
        UniqueConstraint('publicacion_id', 'prestador_id', name='uq_prestador_solicitud')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    publicacion_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    prestador_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    precio_ofertado: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    disponibilidad: Mapped[str] = mapped_column(String(100), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[EstadoPostulacion] = mapped_column(Enum(EstadoPostulacion, values_callable=lambda cls: [member.value for member in cls], name='estado_postulacion'), nullable=False, server_default=text("'pendiente'::estado_postulacion"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))

    prestador: Mapped['Prestadores'] = relationship('Prestadores', back_populates='postulaciones')
    conversaciones: Mapped['Conversaciones'] = relationship('Conversaciones', uselist=False, back_populates='postulaciones')


class Servicios(Base):
    __tablename__ = 'servicios'
    __table_args__ = (
        ForeignKeyConstraint(['categoria_id'], ['categorias.id'], ondelete='RESTRICT', name='servicios_categoria_id_fkey'),
        ForeignKeyConstraint(['prestador_id'], ['prestadores.id'], ondelete='CASCADE', name='servicios_prestador_id_fkey'),
        PrimaryKeyConstraint('id', name='servicios_pkey'),
        Index('idx_servicios_busqueda', 'activo', 'precio_desde'),
        Index('idx_servicios_categoria', 'categoria_id'),
        Index('idx_servicios_prestador', 'prestador_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    prestador_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    categoria_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    precio_desde: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    precio_hasta: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    duracion_estimada: Mapped[int] = mapped_column(Integer, nullable=False)
    activo: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    fecha_publicacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    fecha_creacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    categoria: Mapped['Categorias'] = relationship('Categorias', back_populates='servicios')
    prestador: Mapped['Prestadores'] = relationship('Prestadores', back_populates='servicios')


class Conversaciones(Base):
    __tablename__ = 'conversaciones'
    __table_args__ = (
        ForeignKeyConstraint(['id_postulacion'], ['postulaciones.id'], ondelete='CASCADE', name='fk_postulacion'),
        PrimaryKeyConstraint('id_conversacion', name='conversaciones_pkey'),
        UniqueConstraint('id_postulacion', name='uq_conversaciones_postulacion')
    )

    id_conversacion: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    id_postulacion: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'activa'::character varying"))

    postulaciones: Mapped['Postulaciones'] = relationship('Postulaciones', back_populates='conversaciones')
    mensajes: Mapped[list['Mensajes']] = relationship('Mensajes', back_populates='conversaciones')


class Mensajes(Base):
    __tablename__ = 'mensajes'
    __table_args__ = (
        ForeignKeyConstraint(['id_conversacion'], ['conversaciones.id_conversacion'], ondelete='CASCADE', name='fk_conversacion'),
        ForeignKeyConstraint(['id_destinatario'], ['usuarios.id'], name='fk_destinatario'),
        ForeignKeyConstraint(['id_remitente'], ['usuarios.id'], name='fk_remitente'),
        PrimaryKeyConstraint('id_mensaje', name='mensajes_pkey')
    )

    id_mensaje: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_hora: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    id_conversacion: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    id_remitente: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    id_destinatario: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    conversaciones: Mapped[Optional['Conversaciones']] = relationship('Conversaciones', back_populates='mensajes')
    usuarios: Mapped[Optional['Usuarios']] = relationship('Usuarios', foreign_keys=[id_destinatario], back_populates='mensajes_id_destinatario')
    usuarios_: Mapped[Optional['Usuarios']] = relationship('Usuarios', foreign_keys=[id_remitente], back_populates='mensajes_id_remitente')
