-- 002_seed_subjects.sql
-- Seeds `subjects` from vocab.py's VOCAB dict. Python is the source of
-- truth, one direction only (see vocab.py's module docstring) — if VOCAB
-- changes, this file must be updated by hand to match, never the reverse.

insert into subjects (id, display, synonyms, family) values
    ('red_fox', 'red fox', array['fox', 'red fox', 'vulpes vulpes', 'silver fox'], 'canid'),
    ('gray_wolf', 'gray wolf', array['wolf', 'grey wolf', 'gray wolf', 'canis lupus', 'timber wolf'], 'canid'),
    ('domestic_dog', 'dog', array['dog', 'puppy', 'canis familiaris', 'husky', 'shepherd'], 'canid'),
    ('red_panda', 'red panda', array['red panda', 'ailurus fulgens', 'lesser panda'], 'musteloid'),
    ('raccoon', 'raccoon', array['raccoon', 'procyon lotor', 'racoon'], 'musteloid'),
    ('domestic_cat', 'cat', array['cat', 'kitten', 'felis catus'], 'feline'),
    ('unknown', 'unknown', array[]::text[], null);
