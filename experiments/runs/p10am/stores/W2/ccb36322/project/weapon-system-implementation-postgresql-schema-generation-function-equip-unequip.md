---
name: weapon-system-implementation-postgresql-schema-generation-function-equip-unequip
abstract: "Weapon system implementation: PostgreSQL schema, generation function, equip/unequip logic"
type: procedure
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2026-09-02
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Database: Create weapons table with weapon_id, weapon_type, rarity, elemental_damage_type, bonus_ability. Add equipped_weapon_id column to dittobitty table. Implement generate_weapon(rarity) function that creates random weapons; insert_weapon_into_database() persists them; equip_weapon() and unequip_weapon() manage dittobitty equipment. Rarity R generates one random elemental type; UR excludes earth. Bonus ability assigned by weapon type. Modify battle system to calculate damage accounting for weapon properties, elemental effects, and action point costs.
