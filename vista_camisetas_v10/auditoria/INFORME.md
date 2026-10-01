# Reconciliación de los datos de camisetas

El recálculo de los cuatro CSV originales con el motor v5 confirma **8469 candidatos y 998 personas con más de una camiseta**. Las métricas del JSON recibido con las fotos coinciden exactamente con las del motor v2 en los 8469 casos. No es un problema del scraper de imágenes: éste conservó los indicadores de su JSON de entrada.

| Control | Resultado |
|---|---:|
| Candidatos en ambas versiones | 8469 |
| Más de una camiseta en v2 | 1157 |
| Más de una camiseta con las reglas finales v5 | 998 |
| Personas cuyo número de camisetas cambia | 336 |
| Personas que dejan de superar una camiseta | 159 |
| Diferencias en el total de postulaciones | 0 |
| Clasificaciones pendientes | 0 |
| Fotos conservadas | 8463 |

La versión v5 incorpora las equivalencias de partidos confirmadas, excluye las organizaciones locales e independientes clasificadas como no computables y absorbe las alianzas cuando corresponde a integrantes de la trayectoria. El historial de afiliaciones no determina el número de camisetas. Para los indicadores de afiliación se utiliza exclusivamente el registro vigente del partido actual y las fechas válidas.

## Ejemplo: Luis Felipe de la Mata Martínez, DNI 06743534

El conteo pasa de seis camisetas en v2 a tres en v5. Alternativa Breñense y Movimiento Independiente Vamos Vecino dejan de sumar camisetas; sus participaciones electorales se conservan. FreDemo se absorbe en Acción Popular porque esa organización aparece en su trayectoria. La candidatura actual queda incluida.

## Indicadores de afiliación

| Corte | Fechas válidas v2 | Fechas válidas v5 |
|---|---:|---:|
| 7 de octubre de 2025 | 1779 | 1960 |
| 7 de enero de 2026 | 2120 | 2319 |

Los resúmenes de afiliación finales se recalcularon desde los mismos candidatos v5 y coinciden con los que ya utilizaba la web. No se sustituyeron por los indicadores antiguos del archivo de fotos.

## Fuente única del frente

La página por HTTP/HTTPS ahora lee `data/datos.json`. Se eliminaron los datos incrustados en `index.html`. Para abrir la página directamente con doble clic se produce automáticamente `data/datos-local.js`, con exactamente el mismo contenido. Los JSON individuales y la exportación con fotos se generan juntos; un verificador comprueba su igualdad. El proceso `actualizar_datos.py` reconstruye todo desde los CSV y el mapa de imágenes.

Se conserva el diseño, las fotos por DNI, los logos y los dos espacios para logos manuales. No se ha desplegado la página ni incorporado la propuesta editorial.

## Validaciones realizadas

Se verificaron las reglas de genealogías, organizaciones locales y regionales, alianzas, accesitarios, afiliación vigente y límites de ventanas temporales. También se comprobaron la consistencia de los resúmenes por partido y afiliación, y la igualdad del JSON canónico, las exportaciones y la copia local.

Las pruebas del frente en DOM simulado comprobaron los modos HTTPS y archivo local, los 998 casos, el comparador, las rutas de imágenes, los logos y las ocho combinaciones de fecha y período.

`diferencias_por_dni.csv` permite revisar los 336 casos, con los troncos anteriores y nuevos y las reglas aplicadas. `reconciliacion.json` contiene los resultados de los controles. `data/manifest.json` registra huellas SHA256 de las fuentes y del JSON canónico.
