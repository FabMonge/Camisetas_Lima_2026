#!/usr/bin/env python3
"""Generador ERM 2026. Python 3.10+, sin dependencias externas.
Las equivalencias suministradas por el usuario son reglas editoriales provisionales.
Aplica equivalencias, alianzas y clasificaciones confirmadas por el usuario.
"""
import argparse
import csv
import json
import re
import unicodedata
import calendar
from datetime import date, datetime, timedelta
from collections import Counter, defaultdict
from pathlib import Path

CORTES_AFILIACION = ('2025-10-07', '2026-01-07')


def fecha(valor):
    if not valor:
        return None
    for formato in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(valor, formato).date()
        except ValueError:
            pass
    raise ValueError(f'Fecha inválida: {valor!r}')


def seis_meses_antes(corte):
    mes = corte.year * 12 + corte.month - 1 - 6
    year, month = divmod(mes, 12)
    month += 1
    return date(year, month, min(corte.day, calendar.monthrange(year, month)[1]))


def afiliacion_al_corte(historial, partido, mapa, corte):
    """Solo afiliación vigente del tronco actual; históricos no se calculan."""
    objetivo = tronco(partido, mapa)
    relevantes = [h for h in historial if normalizar(h.get('rol')) == 'VIGENTE' and tronco(h['partido'], mapa) == objetivo]
    periodos, errores, descartados = set(), [], 0
    for h in relevantes:
        try:
            fin = fecha(h.get('fechaFin'))
            # Un periodo terminado antes del corte no puede determinar la
            # antigüedad al corte, aunque su inicio sea desconocido.
            if fin is not None and fin <= corte:
                descartados += 1
                continue
            inicio = fecha(h.get('fechaInicio'))
            if inicio is None or (fin is None and normalizar(h.get('rol')) != 'VIGENTE'):
                raise ValueError('Periodo sin inicio o historial sin fecha de término')
            if fin and fin < inicio:
                raise ValueError('Término anterior al inicio')
            periodos.add((inicio, fin))
        except ValueError as e:
            errores.append(str(e))
    activos = {(i, f) for i, f in periodos if i <= corte and (f is None or corte < f)}
    estado = ('fechas_incompletas_o_invalidas' if errores else
              'periodos_superpuestos' if len(activos) > 1 else
              'valido' if activos else
              'sin_afiliacion_vigente_al_partido_actual' if not relevantes else
              'afiliacion_posterior_al_corte' if any(i > corte for i, _ in periodos) else
              'sin_periodo_activo_al_corte')
    inicio = next(iter(activos))[0] if estado == 'valido' else None
    dias = (corte - inicio).days if inicio else None
    return {'estado': estado, 'fechaInicioSeleccionada': inicio.isoformat() if inicio else None,
            'antiguedadDias': dias,
            'ultimoDia': dias == 0 if inicio else None,
            'ultimos7Dias': 0 <= dias <= 6 if inicio else None,
            'ultimos30Dias': 0 <= dias <= 29 if inicio else None,
            'ultimos6Meses': seis_meses_antes(corte) < inicio <= corte if inicio else None,
            'hayAfiliacionesPosteriores': any(i > corte for i, _ in periodos),
            'errores': errores, 'datoDisponible': estado == 'valido',
            'valorPresentacion': dias if inicio else 'ND'}


def resumir_afiliaciones(candidatos):
    salida = []
    for corte in CORTES_AFILIACION:
        grupos = defaultdict(list)
        for c in candidatos:
            grupos[c['partidoActual']].append(c['afiliacionReferencias'][corte])
        for partido, registros in sorted(grupos.items()):
            validos = [r for r in registros if r['estado'] == 'valido']
            n, total = len(validos), len(registros)
            ventanas = {}
            for campo in ('ultimoDia', 'ultimos7Dias', 'ultimos30Dias', 'ultimos6Meses'):
                cantidad = sum(r[campo] for r in validos)
                ventanas[campo] = {'cantidad': cantidad,
                                  'pctSobreTotalCandidatos': round(100 * cantidad / total, 2),
                                  'pctSobreAfiliacionesValidas': round(100 * cantidad / n, 2) if n else None}
            promedio = sum(r['antiguedadDias'] for r in validos) / n if n else None
            salida.append({'fechaReferencia': corte, 'partido': partido,
                           'totalCandidatos': total, 'afiliacionesValidas': n,
                           'coberturaPct': round(100 * n / total, 2),
                           'antiguedadPromedioDias': round(promedio, 2) if promedio is not None else None,
                           'antiguedadPromedioAnios': round(promedio / 365.2425, 4) if promedio is not None else None,
                           'estadosDatos': dict(Counter(r['estado'] for r in registros)),
                           'ventanas': ventanas})
    return salida


def normalizar(texto):
    texto = ''.join(c for c in unicodedata.normalize('NFKD', texto or '')
                    if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^A-Za-z0-9\s]', ' ', texto).upper().split())


# Mismo contenido político que la propuesta recuperada, con claves normalizadas.
GRUPOS = {
    'CAMBIO 90 / PERU PATRIA SEGURA': ['CAMBIO 90', 'NUEVA MAYORIA', 'CAMBIO 90 - NUEVA MAYORIA', 'CAMBIO 90 NUEVA MAYORIA', 'SI CUMPLE', 'PERU PATRIA SEGURA', 'PARTIDO POLITICO PERU PATRIA SEGURA'],
    'FUERZA POPULAR': ['FUERZA 2011', 'PARTIDO POLITICO FUERZA 2011', 'FUERZA POPULAR', 'PARTIDO POLITICO FUERZA POPULAR'],
    'SOLIDARIDAD NACIONAL / RENOVACION POPULAR': ['SOLIDARIDAD NACIONAL', 'PARTIDO SOLIDARIDAD NACIONAL', 'RENOVACION POPULAR', 'PARTIDO POLITICO RENOVACION POPULAR', 'RENOVACION POPULAR PERU'],
    'RESTAURACION NACIONAL / VICTORIA NACIONAL': ['RESTAURACION NACIONAL', 'PARTIDO RESTAURACION NACIONAL', 'VICTORIA NACIONAL', 'PARTIDO POLITICO VICTORIA NACIONAL'],
    'PPK / CONTIGO': ['PERUANOS POR EL KAMBIO', 'PARTIDO POLITICO PERUANOS POR EL KAMBIO', 'CONTIGO', 'PARTIDO POLITICO CONTIGO'],
    'SIEMPRE UNIDOS / RUNA': ['SIEMPRE UNIDOS', 'PARTIDO POLITICO SIEMPRE UNIDOS', 'RENACIMIENTO UNIDO NACIONAL', 'RUNA'],
    'PODEMOS PERU': ['PODEMOS POR EL PROGRESO DEL PERU', 'PODEMOS PERU', 'PARTIDO POLÍTICO PODEMOS PERU'],
    'FIM / FRENTE DE LA ESPERANZA': ['FRENTE INDEPENDIENTE MORALIZADOR', 'FIM', 'FRENTE DE LA ESPERANZA 2021', 'PARTIDO FRENTE DE LA ESPERANZA 2021'],
    'PARTIDO APRISTA PERUANO': ['PARTIDO APRISTA PERUANO', 'APRA', 'ALIANZA POPULAR REVOLUCIONARIA AMERICANA'],
    'ACCION POPULAR': ['ACCION POPULAR', 'PARTIDO ACCION POPULAR'],
    'SOMOS PERU': ['PARTIDO DEMOCRATICO SOMOS PERU', 'SOMOS PERU', 'MOVIMIENTO INDEPENDIENTE SOMOS PERU'],
    'ALIANZA PARA EL PROGRESO': ['ALIANZA PARA EL PROGRESO', 'PARTIDO POLITICO ALIANZA PARA EL PROGRESO', 'ALIANZA PARA EL PROGRESO DEL PERU'],
    'PPC': ['PARTIDO POPULAR CRISTIANO', 'PARTIDO POPULAR CRISTIANO - PPC', 'PPC'],
    'AVANZA PAIS': ['AVANZA PAIS', 'AVANZA PAIS - PARTIDO DE INTEGRACION SOCIAL', 'PARTIDO POLITICO AVANZA PAIS'],
    'UNION POR EL PERU': ['UNION POR EL PERU', 'UPP'],
    'PARTIDO MORADO': ['PARTIDO MORADO'],
    'PERU LIBRE': ['PARTIDO POLITICO NACIONAL PERU LIBRE', 'PERU LIBRE', 'PERU LIBERTARIO', 'PARTIDO POLITICO PERU LIBERTARIO'],
    'HUMANISTA / JUNTOS POR EL PERU': ['PARTIDO HUMANISTA PERUANO', 'JUNTOS POR EL PERU', 'PARTIDO POLITICO JUNTOS POR EL PERU'],
    'PERU POSIBLE': ['PERU POSIBLE', 'PARTIDO POLITICO PERU POSIBLE', 'PAIS POSIBLE'],
}

# Equivalencias confirmadas por el usuario en esta conversación.
for raiz, nombres in {
    'PERU LIBRE': ['MOVIMIENTO POLITICO REGIONAL PERU LIBRE'],
    'CAMBIO 90 / PERU PATRIA SEGURA': ['AGRUPACION INDEPENDIENTE SI CUMPLE', 'ALIANZA ELECTORAL CAMBIO 90 - NUEVA MAYORIA'],
    'HUMANISTA / JUNTOS POR EL PERU': ['PARTIDO MOVIMIENTO HUMANISTA PERUANO'],
    'PERU POSIBLE': ['PARTIDO PERU POSIBLE'],
    'UNION POR EL PERU': ['AGRUPACION INDEPENDIENTE UNION POR EL PERU - SOCIAL DEMOCRACIA', 'AGRUPACION INDEPENDIENTE UNION POR EL PERU - FRENTE AMPLIO'],
    'PPC': ['PARTIDO POPULAR CRISTIANO - PPC - UNIDAD NACIONAL'],
    'CAMBIO RADICAL': ['CAMBIO RADICAL', 'AGRUPACION INDEPENDIENTE AVANCEMOS'],
    'PERU NACION': ['PERU NACION', 'PARTIDO POLITICO PERU ACCION'],
    'PROYECTO PAIS': ['PROYECTO PAIS', 'PARTIDO PROYECTO PAIS'],
    'FREPAP': ['FRENTE POPULAR AGRICOLA FIA DEL PERU', 'FRENTE POPULAR AGRICOLA FIA DEL PERU - FREPAP'],
    'IZQUIERDA UNIDA': ['IZQUIERDA UNIDA', 'FRENTE ELECTORAL IZQUIERDA UNIDA', 'ALIANZA ELECTORAL IZQUIERDA UNIDA'],
    'FRENATRACA': ['FRENATRACA', 'FRENTE NACIONAL DE TRABAJADORES Y CAMPESINOS - FRENATRACA', 'PERU AL 2000 - FRENATRACA'],
}.items():
    GRUPOS.setdefault(raiz, []).extend(nombres)

ALIANZAS = {
    'ALIANZA:UNIDAD NACIONAL': {'nombres': ['UNIDAD NACIONAL', 'ALIANZA ELECTORAL UNIDAD NACIONAL'], 'miembros': ['PPC', 'SOLIDARIDAD NACIONAL', 'RENOVACION NACIONAL']},
    'ALIANZA:SOLIDARIDAD NACIONAL': {'nombres': ['ALIANZA SOLIDARIDAD NACIONAL', 'ALIANZA ELECTORAL SOLIDARIDAD NACIONAL'], 'miembros': ['CAMBIO 90', 'SIEMPRE UNIDOS', 'UNION POR EL PERU', 'TODOS POR EL PERU', 'SOLIDARIDAD NACIONAL']},
    'ALIANZA:SOLIDARIDAD NACIONAL UPP': {'nombres': ['ALIANZA ELECTORAL SOLIDARIDAD NACIONAL - UPP'], 'miembros': ['SOLIDARIDAD NACIONAL', 'UNION POR EL PERU']},
    'ALIANZA:POR EL GRAN CAMBIO': {'nombres': ['ALIANZA POR EL GRAN CAMBIO'], 'miembros': ['ALIANZA PARA EL PROGRESO', 'RESTAURACION NACIONAL', 'PPC', 'PARTIDO HUMANISTA PERUANO']},
    'ALIANZA:POPULAR': {'nombres': ['ALIANZA POPULAR'], 'miembros': ['PARTIDO APRISTA PERUANO', 'PPC', 'VAMOS PERU']},
    'ALIANZA:FREDEMO': {'nombres': ['FREDEMO'], 'miembros': ['MOVIMIENTO LIBERTAD', 'ACCION POPULAR', 'PPC', 'PARTIDO SOLIDARIDAD Y DEMOCRACIA']},
    'ALIANZA:FRENTE DE CENTRO': {'nombres': ['FRENTE DE CENTRO'], 'miembros': ['ACCION POPULAR', 'SOMOS PERU', 'COORDINADORA NACIONAL DE INDEPENDIENTES']},
    'ALIANZA:GANA PERU': {'nombres': ['GANA PERU'], 'miembros': ['PARTIDO NACIONALISTA PERUANO']},
    'ALIANZA:VAMOS VECINO': {'nombres': ['ALIANZA ELECTORAL VAMOS VECINO', 'ALIANZA ELECTORAL SOLUCION POPULAR'], 'miembros': ['MOVIMIENTO INDEPENDIENTE VAMOS VECINO']},
}


TIPO_ALIAS = {
    'MOVIMIENTO INDEPENDIENTE "DIALOGO VECINAL"': 'DIALOGO VECINAL',
    'ORGANIZACION POLITICA LOCAL PROVINCIAL DIALOGO VECINAL': 'DIALOGO VECINAL',
    'U.T. VIVA LA MOLINA': 'VIVA LA MOLINA',
}


CLASIFICACIONES_CONFIRMADAS = {'COOPERACION, VERDAD Y HONRADEZ': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'COOPERACION VERDAD Y HONRADEZ'}, 'MOVIMIENTO INDEPENDIENTE VAMOS VECINO': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE VAMOS VECINO'}, 'SOMOS LIMA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'SOMOS LIMA'}, 'MOVIMIENTO AMPLIO PAIS UNIDO - MAPU': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'MOVIMIENTO AMPLIO PAIS UNIDO MAPU'}, 'JUNTOS SI PODEMOS': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'JUNTOS SI PODEMOS'}, 'CONFIANZA PERU': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'CONFIANZA PERU'}, 'FONAVISTAS DEL PERU': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'FONAVISTAS DEL PERU'}, 'SAN LUIS RENACE': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'SAN LUIS RENACE'}, 'MAGDALENA AVANZA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MAGDALENA AVANZA'}, 'MOVIMIENTO INDEPENDIENTE COMAS CON FE': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE COMAS CON FE'}, 'MOVIMIENTO INDEPENDIENTE NUEVA SOCIEDAD': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE NUEVA SOCIEDAD'}, 'ACUERDO SOCIALISTA DE IZQUIERDA': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'ACUERDO SOCIALISTA DE IZQUIERDA'}, 'IZQUIERDA SOCIALISTA': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'IZQUIERDA SOCIALISTA'}, 'MOVIMIENTO DEMOCRATICO DE IZQUIERDA': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'MOVIMIENTO DEMOCRATICO DE IZQUIERDA'}, 'MOVIMIENTO INDEPENDIENTE SOMOS NUEVA GENERACION': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE SOMOS NUEVA GENERACION'}, 'MOVIMIENTO SOCIAL INDEPENDIENTE': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'MOVIMIENTO SOCIAL INDEPENDIENTE'}, 'SAN BARTOLO SOLIDARIO': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'SAN BARTOLO SOLIDARIO'}, 'A LA VIDA DILE SI': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'A LA VIDA DILE SI'}, 'ACCION Y TRABAJO': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'ACCION Y TRABAJO'}, 'AGRUPACION INDEPENDIENTE EL GALLO DE ORO': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'AGRUPACION INDEPENDIENTE EL GALLO DE ORO'}, 'AHORA SI SAN JUAN': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'AHORA SI SAN JUAN'}, 'ALTERNATIVA BREÑENSE': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'ALTERNATIVA BRENENSE'}, 'ANGELES DE SAN BORJA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'ANGELES DE SAN BORJA'}, 'BLOQUE POPULAR AMAZONICO': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'BLOQUE POPULAR AMAZONICO'}, 'CAMBIEMOS SAN JUAN': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'CAMBIEMOS SAN JUAN'}, 'CHOSICA AHORA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'CHOSICA AHORA'}, 'CODE - PAIS POSIBLE': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'CODE PAIS POSIBLE'}, 'CON FUERZA PERU': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'CON FUERZA PERU'}, 'COORDINADORA NACIONAL DE INDEPENDIENTES': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'COORDINADORA NACIONAL DE INDEPENDIENTES'}, 'DE SAN BARTOLO PARA EL PERU': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'DE SAN BARTOLO PARA EL PERU'}, 'DECIDE': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'DECIDE'}, 'FRENTE AMPLIO DEMOC. ANCONERO': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'FRENTE AMPLIO DEMOC ANCONERO'}, 'FRENTE DE INTEGRACION Y DESARROLLO COMUNAL - FIDEC': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'FRENTE DE INTEGRACION Y DESARROLLO COMUNAL FIDEC'}, 'FRENTE DE SOLIDARIDAD ANCONERA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'FRENTE DE SOLIDARIDAD ANCONERA'}, 'FRENTE INDEPENDIENTE CONCERTACION POR ANCON': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'FRENTE INDEPENDIENTE CONCERTACION POR ANCON'}, 'FRENTE INDEPENDIENTE DEMOCRATICO': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'FRENTE INDEPENDIENTE DEMOCRATICO'}, 'FRENTE PATRIOTA PERUANO': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'FRENTE PATRIOTA PERUANO'}, 'FRENTE POPULAR Y AGROPECUARIO DE CARABAYLLO FREPAC': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'FRENTE POPULAR Y AGROPECUARIO DE CARABAYLLO FREPAC'}, 'FUERZA NACIONAL': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'FUERZA NACIONAL'}, 'JUNIN EMPRENDEDORES RUMBO AL 21': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'JUNIN EMPRENDEDORES RUMBO AL 21'}, 'LA NUEVA OPCION DE PUENTE PIEDRA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'LA NUEVA OPCION DE PUENTE PIEDRA'}, 'MAS SAN MARTIN': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MAS SAN MARTIN'}, 'MOVIMIENTO ACCION NACIONALISTA PERUANO': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'MOVIMIENTO ACCION NACIONALISTA PERUANO'}, 'MOVIMIENTO ACCION SOCIAL INDEPENDIENTE': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'MOVIMIENTO ACCION SOCIAL INDEPENDIENTE'}, 'MOVIMIENTO CIVICO NACIONAL OBRAS': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'MOVIMIENTO CIVICO NACIONAL OBRAS'}, 'MOVIMIENTO DE INTEGRACION LURINENSE': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO DE INTEGRACION LURINENSE'}, 'MOVIMIENTO DE INTEGRACION VILLAMARIANA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO DE INTEGRACION VILLAMARIANA'}, 'MOVIMIENTO ECOLOGICO ALTERNATIVA VERDE - LOS VERDES': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'MOVIMIENTO ECOLOGICO ALTERNATIVA VERDE LOS VERDES'}, 'MOVIMIENTO INDEPENDIENTE "CHOSICA MERECE MAS"': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE CHOSICA MERECE MAS'}, 'MOVIMIENTO INDEPENDIENTE AGRARIO': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE AGRARIO'}, 'MOVIMIENTO INDEPENDIENTE COMUNIDAD CIVICA DE MAGDALENA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE COMUNIDAD CIVICA DE MAGDALENA'}, 'MOVIMIENTO INDEPENDIENTE DE CAMPESINOS Y PROFESIONALES': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE DE CAMPESINOS Y PROFESIONALES'}, 'MOVIMIENTO INDEPENDIENTE DEL PUEBLO Y PARA EL PUEBLO - MIPP': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE DEL PUEBLO Y PARA EL PUEBLO MIPP'}, 'MOVIMIENTO INDEPENDIENTE ECOLOGICO "ARRIBA LORETO"': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE ECOLOGICO ARRIBA LORETO'}, 'MOVIMIENTO INDEPENDIENTE EL GALLO DE ORO': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE EL GALLO DE ORO'}, 'MOVIMIENTO INDEPENDIENTE LA ARBOLEDA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE LA ARBOLEDA'}, 'MOVIMIENTO INDEPENDIENTE PUCUSANA FUERZA Y DESARROLLO': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE PUCUSANA FUERZA Y DESARROLLO'}, 'MOVIMIENTO INDEPENDIENTE REVELACION HUAROCHIRANA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO INDEPENDIENTE REVELACION HUAROCHIRANA'}, 'MOVIMIENTO OBRAS': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'OBRAS'}, 'MOVIMIENTO UNIDOS POR SAN LUIS': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO UNIDOS POR SAN LUIS'}, 'MOVIMIENTO VECINAL SAN MIGUEL SI': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'MOVIMIENTO VECINAL SAN MIGUEL SI'}, 'MUVA': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'MUVA'}, 'NUEVO PUCUSANA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'NUEVO PUCUSANA'}, 'OBRAS': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'OBRAS'}, 'PAN': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'PAN'}, 'PLATAFORMA DEMOCRATICA': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'PLATAFORMA DEMOCRATICA'}, 'PROGRESANDO PERU': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'PROGRESANDO PERU'}, 'PUNTA HERMOSA UNIDO': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'PUNTA HERMOSA UNIDO'}, 'SALVEMOS MIRAFLORES': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'SALVEMOS MIRAFLORES'}, 'SAN LUIS: SOMOS INDEPENDIENTES': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'SAN LUIS SOMOS INDEPENDIENTES'}, 'SOMOS LURIN': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'SOMOS LURIN'}, 'TIERRA Y DIGNIDAD': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'TIERRA Y DIGNIDAD'}, 'TODAS LAS SANGRES': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'TODAS LAS SANGRES'}, 'TODOS POR LA VICTORIA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'TODOS POR LA VICTORIA'}, 'UNIDOS CONSTRUYENDO': {'cuenta': True, 'tipo': 'COMPUTABLE POR CONFIRMACION EDITORIAL', 'identidad': 'UNIDOS CONSTRUYENDO'}, 'UNIDOS POR JULIACA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'UNIDOS POR JULIACA'}, 'UNIDOS SALVEMOS BREÑA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'UNIDOS SALVEMOS BRENA'}, 'UNION SANTA ROSA': {'cuenta': False, 'tipo': 'NO COMPUTABLE LOCAL', 'identidad': 'UNION SANTA ROSA'}}

def clasificar(nombre, mapa, dimensiones, anio_evento=None):
    clave = normalizar(nombre)
    confirmadas = {normalizar(k): v for k, v in CLASIFICACIONES_CONFIRMADAS.items()}
    if clave in confirmadas:
        return {**confirmadas[clave], 'fuente': 'clasificación confirmada por el usuario'}
    for ident, regla in ALIANZAS.items():
        if clave in {normalizar(n) for n in regla['nombres']}:
            if ident == 'ALIANZA:UNIDAD NACIONAL' and anio_evento and int(anio_evento) >= 2025:
                return {'tipo': 'ALIANZA', 'identidad': 'ALIANZA:UNIDAD NACIONAL 2025', 'cuenta': True,
                        'fuente': 'dimensión: alianza inscrita en 2025', 'miembrosPendientes': True}
            return {'tipo': 'ALIANZA', 'identidad': ident, 'cuenta': True, 'fuente': 'regla editorial de alianza'}
    # Equivalencias históricas nacionales prevalecen sobre palabras del nombre.
    if clave in mapa:
        return {'tipo': 'TRONCO COMPUTABLE', 'identidad': tronco(nombre, mapa), 'cuenta': True, 'fuente': 'equivalencia confirmada'}
    alias = {normalizar(k): normalizar(v) for k, v in TIPO_ALIAS.items()}
    dim = dimensiones.get(alias.get(clave, clave))
    if dim:
        tipo = normalizar(dim.get('Tipo partido'))
        cuenta = False if 'LOCAL' in tipo else True if tipo in ('PARTIDO POLITICO', 'MOVIMIENTO REGIONAL', 'ALIANZA ELECTORAL') else None
        return {'tipo': tipo, 'identidad': ('ALIANZA:' if tipo == 'ALIANZA ELECTORAL' else '') + clave,
                'cuenta': cuenta, 'fuente': 'dimensión'}
    if clave.startswith(('L I ', 'LISTA INDEPENDIENTE ', 'AGRUPACION VECINAL ', 'ORGANIZACION POLITICA LOCAL ')):
        return {'tipo': 'LOCAL', 'identidad': clave, 'cuenta': False, 'fuente': 'denominación local explícita'}
    if 'REGIONAL' in clave:
        return {'tipo': 'MOVIMIENTO REGIONAL', 'identidad': clave, 'cuenta': True, 'fuente': 'denominación regional explícita'}
    if clave.startswith('ALIANZA '):
        return {'tipo': 'ALIANZA', 'identidad': 'ALIANZA:' + clave, 'cuenta': True, 'fuente': 'denominación de alianza explícita'}
    if clave.startswith('PARTIDO '):
        return {'tipo': 'PARTIDO POLITICO', 'identidad': clave, 'cuenta': True, 'fuente': 'denominación de partido explícita'}
    # No convertir un nombre ambiguo en local o nacional por conjetura.
    return {'tipo': 'PENDIENTE', 'identidad': clave, 'cuenta': None, 'fuente': 'sin tipo en dimensión ni regla'}


def construir_mapa(grupos):
    mapa = {}
    for raiz, nombres in grupos.items():
        for nombre in nombres + [raiz]:
            clave = normalizar(nombre)
            if clave in mapa and mapa[clave] != raiz:
                raise ValueError(f'Equivalencia contradictoria: {nombre}')
            mapa[clave] = raiz
    return mapa


def tronco(nombre, mapa):
    clave = normalizar(nombre)
    return mapa.get(clave, clave) if clave else None


def id_web(nombre):
    # Replica normalizarId de app.js, sin colapsar guiones con espacios.
    s = ''.join(c for c in unicodedata.normalize('NFD', nombre.lower())
                if not unicodedata.combining(c))
    return re.sub('_+', '_', re.sub('[^a-z0-9]', '_', s)).rstrip('_')


def leer(path, columnas):
    with path.open(encoding='utf-8-sig', newline='') as f:
        lector = csv.DictReader(f)
        faltan = set(columnas) - set(lector.fieldnames or [])
        if faltan:
            raise ValueError(f'{path.name}: faltan columnas {sorted(faltan)}')
        return [{k: (v or '').strip() for k, v in r.items()} for r in lector]


def dni(valor):
    if not re.fullmatch(r'\d{1,8}', valor):
        raise ValueError(f'DNI inválido: {valor!r}; leer como texto, no como número.')
    return valor.zfill(8)


def anio(proceso):
    encontrados = re.findall(r'\b(?:19|20)\d{2}\b', proceso)
    if len(encontrados) != 1:
        raise ValueError(f'Año no inequívoco: {proceso!r}')
    return int(encontrados[0])


def unicos(registros):
    vistos, salida = set(), []
    for r in registros:
        clave = json.dumps(r, sort_keys=True, ensure_ascii=False)
        if clave not in vistos:
            vistos.add(clave)
            salida.append(r)
    return salida


def metricas(historial, actuales, mapa, actual_anio, dimensiones=None):
    dimensiones = dimensiones or {}
    eventos = historial + [dict(anio=str(actual_anio), partido=r['organizacion_politica']) for r in actuales]
    eventos = [{**h, 'clasificacion': clasificar(h['partido'], mapa, dimensiones, h['anio'])} for h in eventos]
    computables = [h for h in eventos if h['clasificacion']['cuenta'] is True]
    directos = {h['clasificacion']['identidad'] for h in computables if h['clasificacion']['identidad'] not in ALIANZAS}
    equivalencias = {}
    for ident, regla in ALIANZAS.items():
        miembros = {tronco(n, mapa) for n in regla['miembros']}
        equivalencias[ident] = miembros & directos
    raices = set(directos)
    por_anio = defaultdict(set)
    absorciones = []
    ambigua_alianza = False
    for h in computables:
        ident = h['clasificacion']['identidad']
        opciones = equivalencias.get(ident, set())
        if opciones:
            absorciones.append({'anio': h['anio'], 'alianza': h['partido'], 'integrantesEnTrayectoria': sorted(opciones)})
            if len(opciones) != 1:
                ambigua_alianza = True
                continue
            ident = next(iter(opciones))
        else:
            raices.add(ident)
        por_anio[int(h['anio'])].add(ident)
    pendientes = sorted({h['partido'] for h in eventos if h['clasificacion']['cuenta'] is None})
    miembros_pendientes = sorted({h['partido'] for h in eventos if h['clasificacion'].get('miembrosPendientes')})
    ambiguo = ambigua_alianza or any(len(t) > 1 for t in por_anio.values()) or bool(pendientes)
    secuencia = [next(iter(por_anio[a])) for a in sorted(por_anio)] if not ambiguo else []
    saltos = sum(a != b for a, b in zip(secuencia, secuencia[1:])) if not ambiguo else None
    return {'camisetasDistintas': len(raices), 'saltosCronologicos': saltos,
        'cronologiaAmbigua': ambiguo, 'esCamaleon': len(raices) >= 2,
        'clasificacionCompleta': not pendientes and not miembros_pendientes,
        'organizacionesPendientes': pendientes, 'alianzasMiembrosPendientes': miembros_pendientes,
        'camisetasMaximasConPendientes': len(raices) + len(pendientes),
        'troncosHistoricos': sorted(raices), 'alianzasAbsorbidas': absorciones,
        'postulacionesSinCamiseta': sum(h['clasificacion']['cuenta'] is False for h in eventos),
        'postulacionesHistoricas': len(historial), 'postulacionesActuales': len(actuales),
        'totalPostulaciones': len(historial) + len(actuales),
        'victoriasHistoricas': sum(h['elegido'] == 'SI' for h in historial),
        'derrotasHistoricas': sum(h['elegido'] == 'NO' for h in historial)}


def generar(args):
    base, out = Path(args.entrada), Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)
    grupos = json.loads(Path(args.linajes).read_text(encoding='utf-8')) if args.linajes else GRUPOS
    mapa = construir_mapa(grupos)
    actuales = leer(base / args.candidaturas, ['DNI', 'candidato', 'organizacion_politica', 'cargo', 'departamento', 'provincia', 'tipo_eleccion'])
    elecciones = leer(base / 'hechos_procesos_electorales.csv', ['DNI', 'PROCESO ELECTORAL', 'CARGO AL QUE POSTULÓ', 'ORGANIZACIÓN POLÍTICA', 'CIRCUNSCRIPCIÓN', 'ELEGIDO'])
    afiliaciones = leer(base / 'hechos_afiliaciones.csv', ['DNI_Político', 'Organización Política', 'Tipo_Registro', 'Inicio de afiliación', 'Termino de afiliación'])
    dimensiones = leer(base / 'dim_organizaciones_politicas.csv', ['Organización Política', 'Tipo partido'])
    dim = {normalizar(r['Organización Política']): r for r in dimensiones}
    reporte = {'reglas': {'anio': args.anio, 'departamento': args.departamento, 'provincia': args.provincia,
                         'estados': args.estados or 'TODOS; no equivale a lista final de admitidos',
                         'linajes': 'equivalencias confirmadas por el usuario',
                         'alianzas': 'absorción si aparece un integrante en la trayectoria; no se fusionan integrantes', 'accesitarios': 'excluidos de candidaturas e historial'},
               'filas_candidaturas_entrada': len(actuales)}
    universo = []
    for r in actuales:
        if args.departamento and normalizar(r['departamento']) != normalizar(args.departamento):
            continue
        if args.provincia and normalizar(r['provincia']) != normalizar(args.provincia):
            continue
        if 'ACCESITARIO' in normalizar(r['cargo']):
            continue
        if args.estados and normalizar(r.get('estado_candidato', '')) not in {normalizar(x) for x in args.estados}:
            continue
        r['DNI'] = dni(r['DNI'])
        if not r['organizacion_politica']:
            raise ValueError(f'Candidatura sin partido: {r["DNI"]}')
        universo.append(r)
    antes = len(universo)
    universo = unicos(universo)
    reporte['duplicados_candidaturas_eliminados'] = antes - len(universo)
    if not universo:
        raise ValueError('El filtro no seleccionó candidaturas.')
    agrupados, he, ha = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in universo:
        agrupados[r['DNI']].append(r)
    ids = set(agrupados)
    reporte['accesitarios_historicos_excluidos'] = 0
    reporte['historias_actuales_omitidas_para_evitar_doble_conteo'] = 0
    for r in elecciones:
        ident = dni(r['DNI'])
        if ident not in ids:
            continue
        if 'ACCESITARIO' in normalizar(r['CARGO AL QUE POSTULÓ']):
            reporte['accesitarios_historicos_excluidos'] += 1
            continue
        year = anio(r['PROCESO ELECTORAL'])
        if year >= args.anio:
            if year == args.anio and 'REGIONALES Y MUNICIPALES' in normalizar(r['PROCESO ELECTORAL']):
                reporte['historias_actuales_omitidas_para_evitar_doble_conteo'] += 1
                continue
            raise ValueError('Historial contemporáneo/futuro requiere decisión: ' + r['PROCESO ELECTORAL'])
        elegido = normalizar(r['ELEGIDO'])
        he[ident].append({'anio': str(year), 'partido': r['ORGANIZACIÓN POLÍTICA'],
                          'rol': r['CARGO AL QUE POSTULÓ'], 'elegido': elegido if elegido in ('SI', 'NO') else None,
                          'proceso': r['PROCESO ELECTORAL'], 'circunscripcion': r['CIRCUNSCRIPCIÓN'],
                          'tronco': tronco(r['ORGANIZACIÓN POLÍTICA'], mapa)})
    for r in afiliaciones:
        ident = dni(r['DNI_Político'])
        if ident not in ids:
            continue
        inicio, fin = r['Inicio de afiliación'], r['Termino de afiliación']
        desde = inicio[-4:] if inicio else '?'
        vigente = normalizar(r['Tipo_Registro']) == 'VIGENTE'
        ha[ident].append({'anio': f'{desde} - Act.' if vigente else f'{desde} - {fin[-4:] if fin else "?"}',
                          'fechaInicio': inicio or None, 'fechaFin': fin or None,
                          'partido': r['Organización Política'], 'rol': r['Tipo_Registro'],
                          'estado': r.get('Estado de ciudadano', ''), 'tronco': tronco(r['Organización Política'], mapa)})
    fotos = {}
    logos = {}
    if args.master_anterior:
        fotos = {r['dni']: r.get('idFoto') for r in json.loads(Path(args.master_anterior).read_text(encoding='utf-8'))}
    if args.diccionario_anterior:
        logos = {normalizar(v['nombre']): v.get('logo', '') for v in json.loads(Path(args.diccionario_anterior).read_text(encoding='utf-8')).values()}
    candidatos, resumen, nombres = [], {}, set()
    reporte['duplicados_electorales_eliminados'] = 0
    reporte['duplicados_afiliaciones_eliminados'] = 0
    for ident in sorted(ids):
        filas = agrupados[ident]
        partidos = {r['organizacion_politica'] for r in filas}
        nombres_persona = {normalizar(r['candidato']) for r in filas}
        if len(partidos) != 1 or len(nombres_persona) != 1:
            raise ValueError(f'DNI con partidos o nombres actuales contradictorios: {ident}')
        partido = filas[0]['organizacion_politica']
        historial = sorted(unicos(he[ident]), key=lambda h: (int(h['anio']), h['proceso'], h['rol'], h['partido']))
        afiliacion = unicos(ha[ident])
        reporte['duplicados_electorales_eliminados'] += len(he[ident]) - len(historial)
        reporte['duplicados_afiliaciones_eliminados'] += len(ha[ident]) - len(afiliacion)
        for h in historial:
            h['clasificacion'] = clasificar(h['partido'], mapa, dim, h['anio'])
        m = metricas(historial, filas, mapa, args.anio, dim)
        c = {'dni': ident, 'nombre': filas[0]['candidato'], 'partidoActual': partido, 'clasificacionActual': clasificar(partido, mapa, dim, args.anio),
             'cargos': sorted({r['cargo'] for r in filas}), 'idFoto': fotos.get(ident),
             'historialElectoral': historial, 'historialPartidario': afiliacion,
             'candidaturasActuales': [{k: r.get(k, '') for k in ['cargo', 'tipo_eleccion', 'departamento', 'provincia', 'distrito', 'estado_lista', 'estado_candidato']} for r in filas],
             'anioActual': args.anio, 'metricas': m,
             'cobertura': {'tieneRegistrosElectorales': bool(historial), 'tieneRegistrosAfiliacion': bool(afiliacion),
                          'historialElectoralVacio': 'Sin postulaciones previas, según confirmación del usuario de scraping completo por DNI.',
                          'advertenciaAfiliaciones': 'Ausencia de afiliación no equivale a ausencia de postulaciones.'}}
        candidatos.append(c)
        c['afiliacionReferencias'] = {corte: afiliacion_al_corte(afiliacion, partido, mapa, date.fromisoformat(corte))
                                     for corte in CORTES_AFILIACION}
        s = resumen.setdefault(partido, {'partido': partido, 'totalCandidatos': 0, 'camaleonesObservados': 0, 'conHistorialElectoral': 0})
        s['totalCandidatos'] += 1
        s['camaleonesObservados'] += int(m['esCamaleon'])
        s['conHistorialElectoral'] += int(bool(historial))
        s['candidatosConClasificacionPendiente'] = s.get('candidatosConClasificacionPendiente', 0) + int(not m['clasificacionCompleta'])
        nombres.add(partido)
        nombres.update(h['partido'] for h in historial + afiliacion if h['partido'])
    nombres.update(r['Organización Política'] for r in dimensiones if r['Organización Política'])
    dim = {normalizar(r['Organización Política']): r for r in dimensiones}
    diccionario = {}
    pendientes = []
    for nombre in sorted(nombres):
        clave = id_web(nombre)
        if clave in diccionario:
            if normalizar(diccionario[clave]['nombre']) != normalizar(nombre):
                raise ValueError(f'Colisión de identificador web: {nombre}')
            diccionario[clave].setdefault('variantes', []).append(nombre)
            continue
        diccionario[clave] = {'nombre': nombre, 'logo': logos.get(normalizar(nombre), ''),
                             'tronco': tronco(nombre, mapa), 'dimension': dim.get(normalizar(nombre)),
                             'equivalenciaExplicita': normalizar(nombre) in mapa, 'clasificacion': clasificar(nombre, mapa, dim)}
        if normalizar(nombre) not in mapa:
            pendientes.append(nombre)
    rankings = []
    for s in resumen.values():
        s['pctCamaleonesObservados'] = round(100 * s['camaleonesObservados'] / s['totalCandidatos'], 2)
        rankings.append(s)
    rankings.sort(key=lambda s: (-s['camaleonesObservados'], s['partido']))
    reporte.update({'candidaturas_seleccionadas': len(universo), 'personas': len(candidatos),
                    'estados_candidatos': dict(Counter(r.get('estado_candidato', '') for r in universo)),
                    'personas_con_historial_electoral': sum(bool(c['historialElectoral']) for c in candidatos),
                    'personas_con_afiliaciones': sum(bool(c['historialPartidario']) for c in candidatos),
                    'camaleones_observados': sum(c['metricas']['esCamaleon'] for c in candidatos),
                    'cronologias_ambiguas': sum(c['metricas']['cronologiaAmbigua'] for c in candidatos),
                    'organizaciones_sin_equivalencia_explicita': pendientes})
    reporte['personas_con_clasificacion_pendiente'] = sum(not c['metricas']['clasificacionCompleta'] for c in candidatos)
    reporte['organizaciones_tipo_pendiente'] = sorted({n for c in candidatos for n in c['metricas']['organizacionesPendientes']})
    reporte['alianzas_miembros_pendientes'] = sorted({n for c in candidatos for n in c['metricas']['alianzasMiembrosPendientes']})
    reporte['postulaciones_locales_sin_camiseta'] = sum(c['metricas']['postulacionesSinCamiseta'] for c in candidatos)
    resumen_afiliaciones = resumir_afiliaciones(candidatos)
    reporte['afiliacion_por_corte'] = {corte: dict(Counter(c['afiliacionReferencias'][corte]['estado'] for c in candidatos))
                                      for corte in CORTES_AFILIACION}
    reporte['reglas']['afiliacion'] = {'cortes': list(CORTES_AFILIACION), 'finPeriodo': 'solo control de consistencia del registro Vigente',
        'ventana7Dias': 'corte menos 6 días hasta corte, inclusive',
        'ventana30Dias': 'corte menos 29 días hasta corte, inclusive',
        'ventana6Meses': 'inicio posterior a corte menos seis meses calendario, hasta corte inclusive',
        'seleccion': 'solo afiliación marcada Vigente al tronco actual; Historial no interviene',
        'alcance': 'análisis descriptivo; no determina habilitación legal'}
    salidas = {'candidatos_super_master.json': candidatos, 'diccionario_partidos.json': diccionario,
               'resumen_partidos.json': rankings, 'resumen_afiliaciones.json': resumen_afiliaciones,
               'auditoria.json': reporte, 'linajes_config.json': grupos, 'alianzas_config.json': ALIANZAS, 'clasificaciones_confirmadas.json': CLASIFICACIONES_CONFIRMADAS}
    for filename, data in salidas.items():
        (out / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in reporte.items() if k != 'organizaciones_sin_equivalencia_explicita'}, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entrada', default='.')
    p.add_argument('--salida', default='json_generados')
    p.add_argument('--candidaturas', default='erm2026_educacion_limpia.csv')
    p.add_argument('--departamento', default='LIMA', help='Vacío: todos los departamentos')
    p.add_argument('--provincia', default='LIMA', help='Vacío: todas las provincias')
    p.add_argument('--anio', type=int, default=2026)
    p.add_argument('--estados', nargs='+', help='Sin opción: conserva todos los estados')
    p.add_argument('--linajes', help='JSON editable raíz -> lista de denominaciones')
    p.add_argument('--master-anterior', help='Opcional: reutiliza solo fotos por DNI')
    p.add_argument('--diccionario-anterior', help='Opcional: reutiliza solo logos por nombre normalizado')
    generar(p.parse_args())


if __name__ == '__main__':
    main()
