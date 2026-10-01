"""Reconstruye una única versión de los datos desde los cuatro CSV y el mapa de imágenes."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def guardar(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def hash_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def ejecutar(entrada, mapa_path, base_recursos='../imagenes_voto_informado/', recalcular=True):
    data = ROOT/'data'; data.mkdir(exist_ok=True)
    if recalcular:
        subprocess.run([sys.executable,str(ROOT/'generar_jsons.py'),'--entrada',str(entrada),
                        '--salida',str(data)],check=True,stdout=subprocess.DEVNULL)
    leer=lambda n:json.loads((data/n).read_text(encoding='utf-8'))
    candidatos=leer('candidatos_super_master.json')
    partidos=leer('diccionario_partidos.json')
    mapa=json.loads(mapa_path.read_text(encoding='utf-8-sig'))
    fotos=0
    for c in candidatos:
        r=mapa['candidatos'].get(c['dni'],{})
        ruta=r.get('ruta') if r.get('estado')=='descargada' else None
        if ruta and not re.fullmatch(r'candidatos/'+c['dni']+r'\.(jpg|jpeg|png|webp|gif)',ruta):
            raise ValueError(f'Foto con ruta ajena al DNI: {c["dni"]}')
        c['idFoto']=ruta
        fotos+=bool(ruta)
    for nombre,r in mapa['partidos'].items():
        if r.get('estado')!='descargada':continue
        ruta=r.get('ruta')
        if not re.fullmatch(r'partidos/\d+\.(jpg|jpeg|png|webp|gif)',ruta or ''):
            raise ValueError(f'Logo con ruta inválida: {nombre}')
        import generar_jsons as g
        k=g.id_web(nombre)
        if k in partidos:partidos[k]['logo']=ruta
        if nombre=='RENOVACION POPULAR PERU' and 'renovacion_popular' in partidos:
            partidos['renovacion_popular']['logo']=ruta
    # Rutas acordadas para los dos logos que el usuario aportará.
    partidos['alianza_para_el_progreso']['logo']='partidos/alianza_para_el_progreso.png'
    partidos['primero_la_gente_comunidad_ecologia_libertad_y_progreso']['logo']='partidos/primero_la_gente.png'
    assert len(candidatos)==len({c['dni'] for c in candidatos})
    assert all(c['metricas']['camisetasDistintas']>=1 and c['metricas']['totalPostulaciones']>=1 for c in candidatos)
    assert all(c['metricas']['clasificacionCompleta'] for c in candidatos)
    resumen_partidos=leer('resumen_partidos.json')
    resumen_afiliaciones=leer('resumen_afiliaciones.json')
    import generar_jsons as g
    for r in resumen_partidos:
        grupo=[c for c in candidatos if c['partidoActual']==r['partido']]
        assert len(grupo)==r['totalCandidatos']
        assert sum(c['metricas']['esCamaleon'] for c in grupo)==r['camaleonesObservados']
    assert g.resumir_afiliaciones(candidatos)==resumen_afiliaciones
    fuentes={p.name:hash_file(p) for p in sorted(entrada.glob('*.csv')) if p.name in
             ['erm2026_educacion_limpia.csv','hechos_procesos_electorales.csv',
              'hechos_afiliaciones.csv','dim_organizaciones_politicas.csv']}
    stats={'candidatos':len(candidatos),'masDeUnaCamiseta':sum(c['metricas']['esCamaleon'] for c in candidatos),
           'conFoto':fotos,'cortesAfiliacion':{corte:sum(r['afiliacionesValidas'] for r in resumen_afiliaciones if r['fechaReferencia']==corte)
                                          for corte in ['2025-10-07','2026-01-07']}}
    paquete={'metadata':{'version':'v6; motor v5 con reglas finales','fuentesSHA256':fuentes,
                         'motorSHA256':hash_file(ROOT/'generar_jsons.py'),
                         'mapaImagenesSHA256':hash_file(mapa_path),
                         'baseFotos':base_recursos.rstrip('/')+'/', 'conteos':stats},
             'candidatos':candidatos,'partidos':partidos,'resumenPartidos':resumen_partidos,
             'resumenAfiliaciones':resumen_afiliaciones}
    guardar(data/'candidatos_super_master.json',candidatos)
    guardar(data/'candidatos_con_fotos.json',candidatos)
    guardar(data/'diccionario_partidos.json',partidos)
    # JSON canónico: la página lo lee por HTTP/HTTPS.
    raw=json.dumps(paquete,ensure_ascii=False,separators=(',',':'))
    (data/'datos.json').write_text(raw,encoding='utf-8')
    # Copia derivada automática para abrir con doble clic, donde fetch no puede leer JSON locales.
    (data/'datos-local.js').write_text('if (location.protocol === "file:") { window.DATOS_V5 = '+raw.replace('</','<\\/')+'; }',encoding='utf-8')
    guardar(data/'manifest.json',{'fuenteFrontend':'datos.json','fallbackLocal':'datos-local.js (generado automáticamente)',
                                'datosSHA256':hash_file(data/'datos.json'),'conteos':stats,'fuentesSHA256':fuentes})
    print(json.dumps(stats,ensure_ascii=False,indent=2))
    return paquete

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entrada',type=Path,required=True,help='Carpeta con los cuatro CSV originales')
    p.add_argument('--mapa',type=Path,required=True,help='mapa_imagenes.json producido por el scraper')
    p.add_argument('--base-recursos',default='../imagenes_voto_informado/',help='Carpeta local o URL pública absoluta de las imágenes')
    a=p.parse_args()
    ejecutar(a.entrada.resolve(),a.mapa.resolve(),a.base_recursos)
