---
name: battle-system-not-yet-implemented-turn-based-architecture-outlined
abstract: Battle system not yet implemented; turn-based architecture outlined
type: fact
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

## Status
Battle system does not exist yet in the codebase. Need to implement from scratch.

## Planned Architecture
Turn-based battle loop with these components:
1. **Battle initiation**: Retrieve dittobitties' stats and equipped weapons, determine turn order by AGI
2. **Turn mechanics**: 
   - Available actions: attack, defend, special ability, use item
   - Calculate damage based on stats, equipped weapons, and bonuses
   - Update health/stats
   - Check victory/defeat conditions
3. **Outcomes**: Award experience, currency, or other rewards to victor

## Key Challenges
- Must integrate equipped weapons system with damage calculations
- Need to handle elemental damage effects (burn, paralysis, slow, life drain bonus damage)
- Weapon-specific abilities must trigger during battles (deflect, AGI bonus, critical strikes, stun)
- Action point system needs definition and integration with weapon costs
