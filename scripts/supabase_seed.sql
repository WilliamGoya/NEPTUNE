CREATE TABLE IF NOT EXISTS vessels (
    mmsi          BIGINT PRIMARY KEY,
    imo           BIGINT,
    name          VARCHAR(120),
    call_sign     VARCHAR(20),
    ship_type     INTEGER,
    flag          VARCHAR(3),
    length_m      DOUBLE PRECISION,
    beam_m        DOUBLE PRECISION,
    first_seen    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    last_seen     TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS ix_vessels_imo       ON vessels (imo);
CREATE INDEX IF NOT EXISTS ix_vessels_name      ON vessels (name);
CREATE INDEX IF NOT EXISTS ix_vessels_last_seen ON vessels (last_seen);

CREATE TABLE IF NOT EXISTS positions (
    id              BIGSERIAL PRIMARY KEY,
    vessel_mmsi     BIGINT NOT NULL REFERENCES vessels(mmsi) ON DELETE CASCADE,
    timestamp       TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    sog_knots       DOUBLE PRECISION,
    cog_degrees     DOUBLE PRECISION,
    heading_degrees DOUBLE PRECISION,
    nav_status      INTEGER
);

CREATE INDEX IF NOT EXISTS ix_positions_mmsi_ts_desc ON positions (vessel_mmsi, timestamp);

CREATE TABLE IF NOT EXISTS watchlist (
    id               BIGSERIAL PRIMARY KEY,
    query            VARCHAR(120) NOT NULL,
    submitted_at     TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    submitted_by_ip  VARCHAR(45),
    matched_mmsi     BIGINT REFERENCES vessels(mmsi) ON DELETE SET NULL,
    CONSTRAINT uq_watchlist_query UNIQUE (query)
);

CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);
INSERT INTO alembic_version (version_num) VALUES ('0001_initial')
  ON CONFLICT (version_num) DO NOTHING;


INSERT INTO vessels (mmsi, imo, name, call_sign, ship_type, flag, length_m, beam_m, first_seen, last_seen) VALUES
    (255805953, 9811000, 'MAERSK SENTOSA',     'CQDV',   70, 'PRT', 399.0, 59.0, NOW() - INTERVAL '30 days',  NOW() - INTERVAL '4 minutes'),
    (538008149, 9525338, 'MSC OSCAR',          'V7AB1',  70, 'MHL', 395.0, 59.0, NOW() - INTERVAL '45 days',  NOW() - INTERVAL '12 minutes'),
    (235103368, 9811049, 'EVER ACE',           'VRMW9',  70, 'GBR', 400.0, 62.0, NOW() - INTERVAL '60 days',  NOW() - INTERVAL '8 minutes'),
    (477553400, 9320244, 'CMA CGM MARCO POLO', 'VRBE5',  70, 'HKG', 396.0, 54.0, NOW() - INTERVAL '90 days',  NOW() - INTERVAL '22 minutes'),
    (636019825, 9839870, 'HMM ALGECIRAS',      'D5RQ5',  70, 'LBR', 400.0, 61.0, NOW() - INTERVAL '50 days',  NOW() - INTERVAL '6 minutes'),
    (566123000, 9776418, 'ONE STORK',          '9V2842', 70, 'SGP', 364.0, 51.0, NOW() - INTERVAL '40 days',  NOW() - INTERVAL '17 minutes'),
    (218765000, 9863237, 'HAPAG-LLOYD BERLIN', 'DDLG2',  70, 'DEU', 400.0, 61.0, NOW() - INTERVAL '25 days',  NOW() - INTERVAL '3 minutes'),
    (244730000, 9314226, 'STELLA',             'PCKQ',   80, 'NLD', 183.0, 32.0, NOW() - INTERVAL '120 days', NOW() - INTERVAL '34 minutes'),
    (538090212, 9776200, 'FRONT FUSION',       'V7A2845',80, 'MHL', 333.0, 60.0, NOW() - INTERVAL '70 days',  NOW() - INTERVAL '15 minutes'),
    (311000898, 9412602, 'BRITISH PROGRESS',   'C6FR2',  80, 'BHS', 250.0, 44.0, NOW() - INTERVAL '80 days',  NOW() - INTERVAL '28 minutes'),
    (636092174, 9803733, 'EAGLE BARENTS',      'A8WA9',  80, 'LBR', 274.0, 48.0, NOW() - INTERVAL '35 days',  NOW() - INTERVAL '11 minutes'),
    (215418000, 9740316, 'AEGEAN HORIZON',     '9HA4521',80, 'MLT', 183.0, 32.0, NOW() - INTERVAL '15 days',  NOW() - INTERVAL '7 minutes'),
    (210567000, 9285354, 'GAS NEPTUNE',        '5BPA3',  80, 'CYP', 290.0, 45.0, NOW() - INTERVAL '55 days',  NOW() - INTERVAL '19 minutes'),
    (215280000, 9456307, 'BLUE STAR DELOS',    '9HA3201',60, 'MLT', 145.0, 24.0, NOW() - INTERVAL '180 days', NOW() - INTERVAL '5 minutes'),
    (247234600, 9210513, 'MOBY DRAGON',        'IBAQ',   60, 'ITA', 175.0, 27.0, NOW() - INTERVAL '200 days', NOW() - INTERVAL '14 minutes'),
    (224118660, 9634048, 'TENACIA',            'EBNG',   60, 'ESP', 211.0, 26.0, NOW() - INTERVAL '90 days',  NOW() - INTERVAL '9 minutes'),
    (311000789, 9697420, 'NORWEGIAN EPIC',     'C6XA5',  60, 'BHS', 329.0, 40.0, NOW() - INTERVAL '110 days', NOW() - INTERVAL '21 minutes'),
    (538090456, 9692690, 'CAPE LEONIDAS',      'V7QA8',  70, 'MHL', 292.0, 45.0, NOW() - INTERVAL '65 days',  NOW() - INTERVAL '26 minutes'),
    (255805612, 9745938, 'PORTUGAL VOYAGER',   'CQDX9',  70, 'PRT', 229.0, 32.0, NOW() - INTERVAL '20 days',  NOW() - INTERVAL '13 minutes'),
    (224089000, 9456501, 'GUARDIAN GIBRALTAR', 'EAVH',   50, 'ESP', 65.0,  14.0, NOW() - INTERVAL '300 days', NOW() - INTERVAL '2 minutes')
ON CONFLICT (mmsi) DO NOTHING;


INSERT INTO positions (vessel_mmsi, timestamp, latitude, longitude, sog_knots, cog_degrees, heading_degrees, nav_status) VALUES
    (255805953, NOW() - INTERVAL '6 hours',     36.10, -3.20,  18.5, 268, 268, 0),
    (255805953, NOW() - INTERVAL '4 hours',     36.05, -3.95,  18.2, 265, 265, 0),
    (255805953, NOW() - INTERVAL '2 hours',     36.02, -4.70,  17.8, 263, 263, 0),
    (255805953, NOW() - INTERVAL '1 hour',      36.00, -5.10,  16.5, 260, 260, 0),
    (255805953, NOW() - INTERVAL '30 minutes',  35.98, -5.30,  14.2, 258, 258, 0),
    (255805953, NOW() - INTERVAL '4 minutes',   35.96, -5.36,  12.0, 255, 255, 0),

    (538008149, NOW() - INTERVAL '5 hours',     36.13, -5.42,  0.2, 0,   180, 1),
    (538008149, NOW() - INTERVAL '3 hours',     36.13, -5.42,  0.1, 0,   180, 1),
    (538008149, NOW() - INTERVAL '1 hour',      36.13, -5.42,  0.0, 0,   180, 1),
    (538008149, NOW() - INTERVAL '12 minutes',  36.13, -5.42,  0.0, 0,   180, 1),

    (235103368, NOW() - INTERVAL '8 hours',     37.50,  4.10,  20.5, 88,  88,  0),
    (235103368, NOW() - INTERVAL '6 hours',     37.65,  5.20,  20.2, 85,  85,  0),
    (235103368, NOW() - INTERVAL '4 hours',     37.78,  6.40,  20.0, 84,  84,  0),
    (235103368, NOW() - INTERVAL '2 hours',     37.92,  7.55,  19.8, 82,  82,  0),
    (235103368, NOW() - INTERVAL '30 minutes',  38.00,  8.20,  19.5, 80,  80,  0),
    (235103368, NOW() - INTERVAL '8 minutes',   38.04,  8.45,  19.4, 80,  80,  0),

    (477553400, NOW() - INTERVAL '6 hours',     39.50,  7.80,  17.0, 270, 270, 0),
    (477553400, NOW() - INTERVAL '4 hours',     39.48,  6.65,  17.3, 268, 268, 0),
    (477553400, NOW() - INTERVAL '2 hours',     39.45,  5.50,  17.1, 267, 267, 0),
    (477553400, NOW() - INTERVAL '22 minutes',  39.43,  4.92,  16.8, 266, 266, 0),

    (636019825, NOW() - INTERVAL '4 hours',     35.78, -5.78,  0.3, 0,   90,  1),
    (636019825, NOW() - INTERVAL '2 hours',     35.78, -5.78,  0.1, 0,   90,  1),
    (636019825, NOW() - INTERVAL '6 minutes',   35.78, -5.78,  0.0, 0,   90,  1),

    (566123000, NOW() - INTERVAL '5 hours',     35.20,  1.50,  16.5, 45,  45,  0),
    (566123000, NOW() - INTERVAL '3 hours',     35.85,  2.00,  16.8, 42,  42,  0),
    (566123000, NOW() - INTERVAL '1 hour',      36.40,  2.40,  16.5, 40,  40,  0),
    (566123000, NOW() - INTERVAL '17 minutes',  36.62,  2.55,  16.2, 40,  40,  0),

    (218765000, NOW() - INTERVAL '3 hours',     36.05, -5.20,  12.5, 270, 270, 0),
    (218765000, NOW() - INTERVAL '1 hour',      36.10, -5.35,  8.0,  290, 290, 0),
    (218765000, NOW() - INTERVAL '3 minutes',   36.13, -5.42,  4.5,  315, 315, 0),

    (244730000, NOW() - INTERVAL '6 hours',     40.20,  0.50,  13.5, 195, 195, 0),
    (244730000, NOW() - INTERVAL '4 hours',     39.65,  0.20,  13.2, 192, 192, 0),
    (244730000, NOW() - INTERVAL '2 hours',     39.10, -0.05,  13.0, 190, 190, 0),
    (244730000, NOW() - INTERVAL '34 minutes',  38.95, -0.12,  12.8, 188, 188, 0),

    (538090212, NOW() - INTERVAL '6 hours',     37.10, 11.20,  14.0, 95,  95,  0),
    (538090212, NOW() - INTERVAL '4 hours',     37.05, 12.00,  14.2, 92,  92,  0),
    (538090212, NOW() - INTERVAL '2 hours',     37.00, 12.85,  14.1, 90,  90,  0),
    (538090212, NOW() - INTERVAL '15 minutes',  36.96, 13.30,  13.9, 88,  88,  0),

    (311000898, NOW() - INTERVAL '8 hours',     37.60, -1.00,  0.0, 0,   45,  5),
    (311000898, NOW() - INTERVAL '4 hours',     37.60, -1.00,  0.0, 0,   45,  5),
    (311000898, NOW() - INTERVAL '28 minutes',  37.60, -1.00,  0.0, 0,   45,  5),

    (636092174, NOW() - INTERVAL '5 hours',     37.80, 14.50,  13.5, 88,  88,  0),
    (636092174, NOW() - INTERVAL '3 hours',     37.85, 15.40,  13.2, 86,  86,  0),
    (636092174, NOW() - INTERVAL '11 minutes',  37.88, 16.20,  13.0, 84,  84,  0),

    (215418000, NOW() - INTERVAL '4 hours',     37.95, 23.65,  10.5, 175, 175, 0),
    (215418000, NOW() - INTERVAL '2 hours',     37.78, 23.70,  10.2, 178, 178, 0),
    (215418000, NOW() - INTERVAL '7 minutes',   37.65, 23.72,  9.8,  180, 180, 0),

    (210567000, NOW() - INTERVAL '6 hours',     43.20, 15.50,  12.0, 135, 135, 0),
    (210567000, NOW() - INTERVAL '4 hours',     42.85, 16.10,  12.2, 138, 138, 0),
    (210567000, NOW() - INTERVAL '2 hours',     42.50, 16.80,  12.1, 140, 140, 0),
    (210567000, NOW() - INTERVAL '19 minutes',  42.40, 17.05,  12.0, 140, 140, 0),

    (215280000, NOW() - INTERVAL '3 hours',     37.95, 23.62,  18.0, 95,  95,  0),
    (215280000, NOW() - INTERVAL '2 hours',     37.85, 24.30,  19.5, 100, 100, 0),
    (215280000, NOW() - INTERVAL '1 hour',      37.65, 25.05,  20.0, 105, 105, 0),
    (215280000, NOW() - INTERVAL '5 minutes',   37.50, 25.32,  19.8, 108, 108, 0),

    (247234600, NOW() - INTERVAL '4 hours',     41.80, 11.20,  21.0, 175, 175, 0),
    (247234600, NOW() - INTERVAL '2 hours',     41.10, 11.05,  21.2, 178, 178, 0),
    (247234600, NOW() - INTERVAL '14 minutes',  40.95, 11.02,  21.0, 180, 180, 0),

    (224118660, NOW() - INTERVAL '5 hours',     39.55,  2.65,  22.0, 85,  85,  0),
    (224118660, NOW() - INTERVAL '3 hours',     39.60,  3.55,  22.5, 88,  88,  0),
    (224118660, NOW() - INTERVAL '1 hour',      39.62,  4.50,  22.2, 90,  90,  0),
    (224118660, NOW() - INTERVAL '9 minutes',   39.62,  4.95,  21.8, 92,  92,  0),

    (311000789, NOW() - INTERVAL '6 hours',     41.20, 12.10,  18.5, 145, 145, 0),
    (311000789, NOW() - INTERVAL '4 hours',     40.80, 12.95,  18.2, 148, 148, 0),
    (311000789, NOW() - INTERVAL '2 hours',     40.40, 13.85,  18.0, 150, 150, 0),
    (311000789, NOW() - INTERVAL '21 minutes',  40.25, 14.18,  17.8, 152, 152, 0),

    (538090456, NOW() - INTERVAL '8 hours',     38.50,  6.20,  11.0, 268, 268, 0),
    (538090456, NOW() - INTERVAL '5 hours',     38.42,  5.05,  11.2, 266, 266, 0),
    (538090456, NOW() - INTERVAL '2 hours',     38.35,  3.85,  11.0, 264, 264, 0),
    (538090456, NOW() - INTERVAL '26 minutes',  38.32,  3.40,  10.8, 263, 263, 0),

    (255805612, NOW() - INTERVAL '6 hours',     37.10, -8.95,  15.5, 5,   5,   0),
    (255805612, NOW() - INTERVAL '4 hours',     37.85, -9.10,  15.2, 8,   8,   0),
    (255805612, NOW() - INTERVAL '2 hours',     38.55, -9.20,  15.0, 10,  10,  0),
    (255805612, NOW() - INTERVAL '13 minutes',  38.78, -9.22,  14.8, 12,  12,  0),

    (224089000, NOW() - INTERVAL '4 hours',     36.13, -5.35,  8.5,  90,  90,  0),
    (224089000, NOW() - INTERVAL '2 hours',     36.10, -5.20,  10.2, 95,  95,  0),
    (224089000, NOW() - INTERVAL '1 hour',      36.08, -5.05,  12.5, 88,  88,  0),
    (224089000, NOW() - INTERVAL '2 minutes',   36.07, -4.95,  14.0, 85,  85,  0)
ON CONFLICT DO NOTHING;


INSERT INTO watchlist (query, submitted_at, submitted_by_ip, matched_mmsi) VALUES
    ('MAERSK SENTOSA',  NOW() - INTERVAL '2 days',  '203.0.113.45',  255805953),
    ('EVER GIVEN',      NOW() - INTERVAL '1 day',   '198.51.100.22', NULL),
    ('538008149',       NOW() - INTERVAL '6 hours', '198.51.100.99', 538008149)
ON CONFLICT (query) DO NOTHING;


SELECT 'vessels'   AS table_name, COUNT(*) AS row_count FROM vessels
UNION ALL
SELECT 'positions',                COUNT(*)             FROM positions
UNION ALL
SELECT 'watchlist',                COUNT(*)             FROM watchlist;
