-- =============================================================================
-- Poblar dim_entidad con las 32 entidades federativas de México
-- Fuente de claves: Catálogo de claves de entidades INEGI
-- =============================================================================

SET search_path TO natalidad_dwh;

INSERT INTO dim_entidad (cve_geo, nombre, region, tipo_zona) VALUES
    ('01', 'Aguascalientes',            'Centro',       'Urbana alta'),
    ('02', 'Baja California',           'Norte',        'Urbana alta'),
    ('03', 'Baja California Sur',       'Norte',        'Urbana media'),
    ('04', 'Campeche',                  'Sur-Sureste',  'Urbana media'),
    ('05', 'Coahuila',                  'Norte',        'Urbana alta'),
    ('06', 'Colima',                    'Centro',       'Urbana media'),
    ('07', 'Chiapas',                   'Sur-Sureste',  'Rural'),
    ('08', 'Chihuahua',                 'Norte',        'Urbana alta'),
    ('09', 'Ciudad de México',          'Centro',       'Urbana alta'),
    ('10', 'Durango',                   'Norte',        'Urbana media'),
    ('11', 'Guanajuato',                'Centro',       'Urbana media'),
    ('12', 'Guerrero',                  'Sur-Sureste',  'Rural'),
    ('13', 'Hidalgo',                   'Centro',       'Urbana media'),
    ('14', 'Jalisco',                   'Centro',       'Urbana alta'),
    ('15', 'México',                    'Centro',       'Urbana alta'),
    ('16', 'Michoacán',                 'Centro',       'Urbana media'),
    ('17', 'Morelos',                   'Centro',       'Urbana media'),
    ('18', 'Nayarit',                   'Centro',       'Urbana media'),
    ('19', 'Nuevo León',                'Norte',        'Urbana alta'),
    ('20', 'Oaxaca',                    'Sur-Sureste',  'Rural'),
    ('21', 'Puebla',                    'Centro',       'Urbana media'),
    ('22', 'Querétaro',                 'Centro',       'Urbana alta'),
    ('23', 'Quintana Roo',              'Sur-Sureste',  'Urbana media'),
    ('24', 'San Luis Potosí',           'Centro',       'Urbana media'),
    ('25', 'Sinaloa',                   'Norte',        'Urbana media'),
    ('26', 'Sonora',                    'Norte',        'Urbana alta'),
    ('27', 'Tabasco',                   'Sur-Sureste',  'Urbana media'),
    ('28', 'Tamaulipas',                'Norte',        'Urbana alta'),
    ('29', 'Tlaxcala',                  'Centro',       'Urbana media'),
    ('30', 'Veracruz',                  'Sur-Sureste',  'Rural'),
    ('31', 'Yucatán',                   'Sur-Sureste',  'Urbana media'),
    ('32', 'Zacatecas',                 'Centro',       'Rural');

-- =============================================================================
-- VERIFICACIÓN
-- =============================================================================
-- SELECT count(*) FROM natalidad_dwh.dim_entidad;   -- esperado: 32
-- SELECT region, count(*) FROM natalidad_dwh.dim_entidad GROUP BY region;
-- SELECT tipo_zona, count(*) FROM natalidad_dwh.dim_entidad GROUP BY tipo_zona;
