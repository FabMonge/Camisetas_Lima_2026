# Camisetas políticas en Lima

Especial interactivo de Fabrizio Monge para El Comercio / ECData.
Versión 13: portada oficial y preparación para Git.

## Carpeta del repositorio

La raíz es CAMISETAS_2_0. Contiene vista_camisetas_v10 y, cuando la copies desde tu computadora, imagenes_voto_informado. Mantén ambas al mismo nivel para que funcionen las rutas a fotos y logos.

El ZIP incluye código, datos, auditorías y portada. No incluye las fotos de candidatos ni los logos de partidos, que debes copiar desde tu carpeta original imagenes_voto_informado, conservando su contenido y estructura.

Abre vista_camisetas_v10/index.html para revisar la página.

## Primera subida desde Windows

1. Instala Git desde https://git-scm.com/install/windows.
2. Crea un repositorio vacío llamado camisetas-lima en https://github.com/new. Puedes elegir Private. No agregues README, licencia ni .gitignore desde GitHub, porque ya están preparados aquí.
3. Extrae el ZIP y copia imagenes_voto_informado dentro de CAMISETAS_2_0.
4. Entra a CAMISETAS_2_0 en el Explorador, escribe powershell en la barra de dirección y presiona Enter.
5. Ejecuta git --version para comprobar la instalación.
6. Ejecuta los siguientes comandos uno a uno. Cambia TU_CORREO por el correo que deseas registrar como autor. Cambia TU_USUARIO por tu usuario de GitHub. Si usaste otro nombre de repositorio, cambia también camisetas-lima.

```powershell
git init -b main
git config user.name "Fabrizio Monge"
git config user.email "TU_CORREO"
git add .
git status
git commit -m "Primera version del especial camisetas"
git remote add origin https://github.com/TU_USUARIO/camisetas-lima.git
git push -u origin main
```

Cuando Git solicite autenticación, inicia sesión en GitHub mediante el navegador si ofrece esa opción.

## Subir cambios posteriores

Desde la misma carpeta:

```powershell
git add .
git commit -m "Actualizar textos y visualizaciones"
git push
```

Subir el repositorio guarda los archivos en GitHub. Publicar la página web es un paso separado.
