---
name: dittobitties-game-weapon-system-with-4-types-4-rarities-elemental-damage-and-uni
abstract: "Dittobitties game: weapon system with 4 types, 4 rarities, elemental damage, and unique bonus abilities"
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

## Weapon System Design

### Weapon Types and Rarities
- **Sword types**: C (basic physical), UC (improved physical), R (mostly physical + random elemental + deflect ability), UR (100% elemental + deflect)
- **Bow types**: C (basic physical), UC (improved physical), R (mostly physical + random elemental + AGI bonus ability), UR (100% elemental + AGI bonus)
- **Axe types**: C (basic physical), UC (improved physical), R (mostly physical + random elemental + crit strike ability), UR (100% elemental + crit strike)
- **Mace types**: C (basic physical), UC (improved physical), R (mostly physical + random elemental + stun ability), UR (100% elemental + stun)

### Weapon-Specific Bonus Abilities
- **Swords**: Chance to deflect incoming attacks
- **Bows**: Bonus damage from player's AGI stat
- **Axes**: Chance to critical strike for 1.8x damage
- **Maces**: Chance to stun opponent (prevents next turn action)

### Elemental Damage Types and Effects
1. **Fire**: Chance to inflict burn (lasting damage)
2. **Lightning**: Small chance to cause paralysis (skip next turn)
3. **Water**: Chance to slow target (vulnerable to lightning)
4. **Life Drain**: Steals 20% of damage dealt, heals user
5. **Earth**: Chance to deal bonus damage

### Action Point Costs by Rarity
- C: uses more action points
- UC: uses slightly fewer action points
- R: uses even fewer action points
- UR: uses slightly fewer action points than R

### Database Schema
- weapons table: weapon_id, weapon_type, rarity, elemental_damage_type, bonus_ability
- dittobitty table: add equipped_weapon_id column
- Weapon generation: rarity-based randomization of elemental damage and bonus abilities
