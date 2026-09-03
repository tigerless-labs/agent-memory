---
name: react-native-link-favorite-locations-to-google-places-navigation-via-redux-dispa
abstract: "React Native: link favorite locations to Google Places navigation via Redux dispatch"
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

Solved by using Redux dispatch + React Navigation. When user presses a favorite location (Home/Work/Business/Game), dispatch setDestination action with {location: coordinates from Google Places, description: place name}, then navigate to RideOptionsCard screen. Uses react-native-maps, react-native-google-places-autocomplete, redux, @react-navigation/native, tailwind-react-native-classnames, react-native-elements Icon, and GOOGLE_MAPS_APIKEY from .env. The NavFavourites component had hardcoded locations in Islamabad (Home: Sector G-9/1, Work: Sector I-9 STP, Business: Olympus F-11, Game: Total F-6).
