1. Instala Docker Desktop si no lo tienes.
2. Crea una carpeta para el proyecto.
3. Coloca ahí el docker-compose.yml.
4. Crea una subcarpeta llamada "db" y coloca seed.sql dentro (ruta: db/seed.sql).
5. Abre PowerShell en esa carpeta y corre:
   docker compose up -d db
6. Espera unos segundos, luego verifica con:
   docker ps
   (deberías ver el contenedor corriendo)
7. Conéctate desde DataGrip con:
   Host: localhost | Puerto: 5432 | Usuario: postgres | Contraseña: 1234 | Base: servia_db