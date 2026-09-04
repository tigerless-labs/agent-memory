---
created: 2026-09-03T01:32:13.125996910Z
updated: 2026-09-03T01:32:13.125996910Z
weight: 1.0
last_accessed: 2026-09-03T01:32:13.125996910Z
access_count: 0
pinned: false
links:
- dittobittys-turn-based-battle-system-outline
abstract: Equipable weapons for attacker role with 4 weapon types (sword, bow, axe, mace), 4 rarities (C, UC, R, UR), 5 elemental damage types, and weapon-specific bonus abilities. Implementation uses PostgreSQL and Python.
---

## Weapon Types & Rarities

### Swords
- **Rarity C**: Basic sword, physical damage, no bonuses, high action point cost
- **Rarity UC**: Improved sword, slightly increased damage, fewer action points
- **Rarity R**: Enhanced sword, mostly physical + random elemental, bonus ability: **chance to deflect incoming attacks**, fewer action points
- **Rarity UR**: 100% elemental damage, chance to deflect incoming attacks, fewer action points

### Bows
- **Rarity C**: Basic bow, physical damage, no bonuses, high action point cost
- **Rarity UC**: Improved bow, slightly increased damage, fewer action points
- **Rarity R**: Enhanced bow, mostly physical + random elemental, bonus ability: **bonus damage based on AGI**, fewer action points
- **Rarity UR**: 100% elemental damage, bonus damage based on AGI, fewer action points

### Axes
- **Rarity C**: Basic axe, physical damage, no bonuses, high action point cost
- **Rarity UC**: Improved axe, slightly increased damage, fewer action points
- **Rarity R**: Enhanced axe, mostly physical + random elemental, bonus ability: **chance to critical strike for 1.8x damage**, fewer action points
- **Rarity UR**: 100% elemental damage, chance to critical strike for 1.8x damage, fewer action points

### Maces
- **Rarity C**: Basic mace, physical damage, no bonuses, high action point cost
- **Rarity UC**: Improved mace, slightly increased damage, fewer action points
- **Rarity R**: Enhanced mace, mostly physical + random elemental, bonus ability: **chance to stun opponent (prevents next turn action)**, fewer action points
- **Rarity UR**: 100% elemental damage, chance to stun opponent, fewer action points

## Elemental Damage Types

- **Fire**: Chance to inflict burn (lasting damage)
- **Lightning**: Small chance of paralysis (target skips next turn)
- **Water**: Chance to slow target (makes them vulnerable to lightning)
- **Life Drain**: Steals 20% of damage dealt and heals user
- **Earth**: Chance to deal bonus damage

## Implementation Overview

**Database (PostgreSQL):**
- New `weapons` table: weapon_id, weapon_type, rarity, elemental_damage_type, bonus_ability
- Add `equipped_weapon_id` column to dittobitty table

**Python Functions:**
- `generate_weapon(rarity)`: Creates random weapon with properties based on rarity
- `insert_weapon_into_database()`: Stores weapon in database
- Equip/unequip functions
- Battle system modifications to apply weapon properties and effects

**Example Code Pattern:**
```python
def generate_weapon(rarity):
    weapon_types = ["sword", "bow", "axe", "mace"]
    elemental_damage_types = ["fire", "lightning", "life_drain", "water", "earth"]
    # Randomly select type and elemental damage
    # Assign bonus_ability based on weapon_type
```