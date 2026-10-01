import sys
import json
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import generar_jsons as g
m = g.construir_mapa(g.GRUPOS)
dim = {g.normalizar('LOCAL A'): {'Tipo partido': 'ORGANIZACION LOCAL (DISTRITAL)'},
       g.normalizar('REGIONAL A'): {'Tipo partido': 'MOVIMIENTO REGIONAL'}}
def h(y, p): return {'anio': str(y), 'partido': p, 'elegido': 'NO'}
def calc(hs, actual): return g.metricas(hs, [{'organizacion_politica': actual}], m, 2026, dim)
assert calc([h(2010, 'PPC'), h(2014, 'LOCAL A')], 'PPC')['camisetasDistintas'] == 1
assert calc([h(2010, 'PPC'), h(2014, 'LOCAL A')], 'PPC')['saltosCronologicos'] == 0
assert calc([h(2010, 'REGIONAL A')], 'PPC')['camisetasDistintas'] == 2
assert calc([h(2000, 'PPC'), h(2006, 'ALIANZA ELECTORAL UNIDAD NACIONAL')], 'PPC')['camisetasDistintas'] == 1
assert calc([h(2006, 'ALIANZA ELECTORAL UNIDAD NACIONAL')], 'PARTIDO OTRO')['camisetasDistintas'] == 2
assert calc([h(2000, 'PPC'), h(2006, 'ALIANZA ELECTORAL UNIDAD NACIONAL')], 'PARTIDO UNIDAD NACIONAL')['camisetasDistintas'] == 2
assert g.clasificar('UNIDAD NACIONAL',m,dim,2026)['identidad'] != g.clasificar('UNIDAD NACIONAL',m,dim,2006)['identidad']
def af(i, rol='Vigente'): return {'partido':'PPC','fechaInicio':i,'rol':rol,'fechaFin':None}
cut=date(2026,1,7)
assert g.afiliacion_al_corte([af('Hasta','Historial'),af('01/01/2026')],'PPC',m,cut)['ultimos7Dias']
assert g.afiliacion_al_corte([af('01/01/2020','Historial')],'PPC',m,cut)['valorPresentacion']=='ND'
assert g.afiliacion_al_corte([af('Hasta')],'PPC',m,cut)['valorPresentacion']=='ND'
assert not g.afiliacion_al_corte([af('31/12/2025')],'PPC',m,cut)['ultimos7Dias']
assert g.afiliacion_al_corte([af('08/01/2026')],'PPC',m,cut)['estado']=='afiliacion_posterior_al_corte'
base=Path(__file__).parent/'data'
d=json.loads((base/'candidatos_super_master.json').read_text())
assert len(d)==len({c['dni'] for c in d})==8469
assert all('ACCESITARIO' not in h['rol'] for c in d for h in c['historialElectoral'])
for c in d:
    assert c['metricas']['totalPostulaciones']==len(c['historialElectoral'])+len(c['candidaturasActuales'])
    for cut in g.CORTES_AFILIACION:
        a=c['afiliacionReferencias'][cut]
        if a['estado']=='valido':
            assert any(g.normalizar(h['rol'])=='VIGENTE' and g.tronco(h['partido'],m)==g.tronco(c['partidoActual'],m) and g.fecha(h['fechaInicio']).isoformat()==a['fechaInicioSeleccionada'] for h in c['historialPartidario'])
assert g.resumir_afiliaciones(d)==json.loads((base/'resumen_afiliaciones.json').read_text())
print('OK: reglas, alianzas, exclusiones, afiliación vigente e integridad del universo.')

assert all(c['metricas']['clasificacionCompleta'] for c in d)
assert g.clasificar('MOVIMIENTO OBRAS',m,dim)['identidad']==g.clasificar('OBRAS',m,dim)['identidad']
assert calc([h(2000,'MOVIMIENTO OBRAS')],'OBRAS')['camisetasDistintas']==1
assert not g.clasificar('ALTERNATIVA BREÑENSE',m,dim)['cuenta']
assert g.clasificar('MOVIMIENTO AMPLIO PAIS UNIDO - MAPU',m,dim)['cuenta']
print('OK: 78 clasificaciones incorporadas; cero pendientes; OBRAS unificado.')

assert all(c['metricas']['camisetasDistintas']>=1 and c['metricas']['totalPostulaciones']>=1 for c in d)
assert calc([h(2011,'FUERZA 2011')],'FUERZA POPULAR')['camisetasDistintas']==1
assert calc([h(2014,'SOLIDARIDAD NACIONAL')],'RENOVACION POPULAR PERU')['camisetasDistintas']==1
assert g.afiliacion_al_corte([af('08/07/2025')],'PPC',m,date(2026,1,7))['ultimos6Meses']
assert not g.afiliacion_al_corte([af('07/07/2025')],'PPC',m,date(2026,1,7))['ultimos6Meses']
paquete=json.loads((base/'datos.json').read_text())
local=(base/'datos-local.js').read_text()
assert local.startswith('if (location.protocol === "file:") { window.DATOS_V5 = ')
local_json=local.split('window.DATOS_V5 = ',1)[1][:-3]
assert json.loads(local_json)==paquete
assert paquete['candidatos']==d
assert paquete['partidos']==json.loads((base/'diccionario_partidos.json').read_text())
assert paquete['resumenPartidos']==json.loads((base/'resumen_partidos.json').read_text())
assert paquete['resumenAfiliaciones']==g.resumir_afiliaciones(d)
assert d==json.loads((base/'candidatos_con_fotos.json').read_text())
assert len(d)==paquete['metadata']['conteos']['candidatos']
assert sum(c['metricas']['esCamaleon'] for c in d)==paquete['metadata']['conteos']['masDeUnaCamiseta']
assert sum(bool(c['idFoto']) for c in d)==paquete['metadata']['conteos']['conFoto']
from collections import Counter
for r in paquete['resumenPartidos']:
    candidatos=[c for c in d if c['partidoActual']==r['partido']]
    assert r['totalCandidatos']==len(candidatos)
    assert r['camaleonesObservados']==sum(c['metricas']['esCamaleon'] for c in candidatos)
for c in d:
    assert c['metricas']['totalPostulaciones']==len(c['historialElectoral'])+len(c['candidaturasActuales'])
    assert all(a['departamento']=='LIMA' and a['provincia']=='LIMA' for a in c['candidaturasActuales'])
    assert all('ACCESITARIO' not in a['cargo'] for a in c['candidaturasActuales'])
print('OK: fuente JSON única, copia local y exportaciones iguales, resúmenes por partido y afiliación consistentes.')
