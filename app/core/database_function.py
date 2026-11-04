from sqlalchemy import text


async def crear_funciones(conn):
    await conn.execute(text("""
        CREATE OR REPLACE FUNCTION public.aceptar_postulacion(
            p_id_postulacion UUID
        )
        RETURNS UUID
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_id_conversacion UUID;
        BEGIN
            UPDATE public.postulaciones
            SET estado = 'aceptada'
            WHERE id = p_id_postulacion
              AND estado = 'pendiente';

            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'La postulacion no existe o no está pendiente';
            END IF;

            UPDATE public.conversaciones
            SET estado = 'activa'
            WHERE id_postulacion = p_id_postulacion
            RETURNING id_conversacion
            INTO v_id_conversacion;

            IF NOT FOUND THEN
                INSERT INTO public.conversaciones (id_postulacion)
                VALUES (p_id_postulacion)
                RETURNING id_conversacion
                INTO v_id_conversacion;
            END IF;

            RETURN v_id_conversacion;
        END;
        $$;
    """))