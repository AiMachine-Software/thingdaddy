-- Step 4 seed: the 7 real verified records (verified + prefix), each with a
-- provenance 'verified' event. Idempotent via ON CONFLICT on the unique prefix.
BEGIN;

WITH seed(prefix, gln, legal_name, city, country, mo, lei) AS (
  VALUES
    ('0702054',    '0702054000004', 'Telular Corporation',           'Chicago',   'US', 'GS1 US',          NULL),
    ('0899728002', '0899728002003', 'Western Research 3000, Inc.',   NULL,        'US', 'GS1 US',          NULL),
    ('8806088',    '8801643000011', 'Samsung Electronics Co., Ltd.', 'Suwon',     'KR', 'GS1 Korea',       NULL),
    ('8719011',     NULL,           'ASML Holding N.V.',             'Veldhoven', 'NL', 'GS1 Netherlands', NULL),
    ('0675900',     NULL,           'Intel Corporation',             'Santa Clara','US','GS1 US',          NULL),
    ('0805795',     NULL,           'Micron Technology, Inc.',       'Boise',     'US', 'GS1 US',          NULL),
    ('0662498',     NULL,           'Honeywell International Inc.',  'Charlotte', 'US', 'GS1 US',          NULL)
)
INSERT INTO party (prefix, gln, legal_name, city, country, mo, lei, state, source, verified_at)
SELECT prefix, gln, legal_name, city, country, mo, lei, 'verified', 'seed', now()
FROM seed
ON CONFLICT (prefix) WHERE prefix IS NOT NULL
DO UPDATE SET state = 'verified', verified_at = now(), source = 'seed';

-- Provenance: one 'verified' event per seeded party (only for freshly seeded ones).
INSERT INTO party_event (party_id, event_type, from_state, to_state, detail, source, actor)
SELECT p.id, 'verified', NULL, 'verified',
       jsonb_build_object('prefix', p.prefix, 'via', 'Step 4 seed'), 'seed', 'manual'
FROM party p
WHERE p.source = 'seed'
  AND NOT EXISTS (
    SELECT 1 FROM party_event e WHERE e.party_id = p.id AND e.event_type = 'verified'
  );

COMMIT;

SELECT id, prefix, legal_name, state, mo FROM party WHERE source = 'seed' ORDER BY id;
