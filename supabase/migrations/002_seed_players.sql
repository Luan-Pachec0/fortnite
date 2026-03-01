-- ============================================================
-- Fortnite Tracker — Seed: Jogadores iniciais
-- Migration 002: Insere os 5 amigos no banco
-- ============================================================

INSERT INTO players (username) VALUES
    ('034 Moreira'),
    ('Aloisio8606'),
    ('Bicho_solto_007'),
    ('Bonnie_Clydee'),
    ('LUAanZeRaaaa')
ON CONFLICT (username) DO NOTHING;
