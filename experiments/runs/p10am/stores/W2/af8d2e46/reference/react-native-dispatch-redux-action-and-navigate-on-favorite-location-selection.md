---
name: react-native-dispatch-redux-action-and-navigate-on-favorite-location-selection
abstract: "React Native: dispatch Redux action and navigate on favorite location selection"
type: reference
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

Implementation pattern for navigation favorites:

When user presses favorite in NavFavourites, dispatch setDestination action to Redux navSlice, then navigate to RideOptionsCard screen.

For Google Places Autocomplete: set fetchDetails=true, extract location data (lat/lng) from details.geometry.location and description from data.description, dispatch both to Redux, then navigate.

Key insight: Redux state machine holds the selected destination so RideOptionsCard can access it independently via useSelector, decoupling the selection screen from the display screen.
