-- Migration 016: add city_size field to cities table
ALTER TABLE cities ADD COLUMN IF NOT EXISTS city_size TEXT
    CHECK (city_size IN ('village', 'small', 'medium', 'large', 'major'));

-- Seed known values
UPDATE cities SET city_size = 'major'  WHERE city IN ('Munich', 'Stuttgart', 'Zurich', 'Innsbruck', 'Salzburg', 'Karlsruhe', 'Nürnberg');
UPDATE cities SET city_size = 'large'  WHERE city IN ('Augsburg', 'Ulm', 'Heidelberg', 'Freiburg', 'Ludwigsburg', 'Ingolstadt', 'Würzburg', 'Tübingen', 'Reutlingen', 'Pforzheim', 'Erlangen', 'Esslingen am Neckar');
UPDATE cities SET city_size = 'medium' WHERE city IN ('Lindau', 'Konstanz', 'Ravensburg', 'Landsberg am Lech', 'Rosenheim', 'Kempten', 'Friedrichshafen', 'Memmingen', 'Kaufbeuren', 'Dachau', 'Landshut', 'Passau', 'Bamberg', 'Garmisch-Partenkirchen', 'Bregenz', 'Dornbirn', 'Feldkirch', 'Basel', 'St. Gallen', 'Winterthur');
