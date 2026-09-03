---
name: equipable-weapons-system-for-dittobitties-4-types-with-rarity-tiers-and-bonus-ab
abstract: "Equipable weapons system for dittobitties: 4 types with rarity tiers and bonus abilities"
type: decision
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-21
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

## Weapon Types & Tiers

- **Swords**: Chance to deflect incoming attacks
- **Bows**: Bonus damage scaled from AGI stat
- **Axes**: Chance to critical strike for 1.8x damage
- **Maces**: Chance to stun opponent (prevents next turn action)

Each weapon type has 4 rarity levels (C, UC, R, UR):
- **C**: Basic, physical damage only, higher action point cost
- **UC**: Improved physical damage, lower action point cost
- **R**: Mostly physical + random elemental damage + weapon-specific bonus ability
- **UR**: 100% elemental damage + weapon-specific bonus ability

## Elemental Damage Types
- Fire: Chance to inflict burn (lasting damage)
- Lightning: Small chance to paralyze (skip next turn)
- Water: Chance to slow target (increases lightning vulnerability)
- Life Drain: Steals 20% of damage dealt to heal user
- Earth: Chance for bonus damage

## Implementation Approach
- PostgreSQL table: weapon_id, weapon_type, rarity, elemental_damage_type, bonus_ability
- Add equipped_weapon_id column to dittobitty table
- Python function to generate weapons with random properties by rarity
- Functions to handle equipping/unequipping weapons
- Integrate weapon properties into battle system
