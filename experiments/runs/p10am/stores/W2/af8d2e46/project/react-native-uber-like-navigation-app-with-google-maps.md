---
name: react-native-uber-like-navigation-app-with-google-maps
abstract: React Native Uber-like navigation app with Google Maps
type: fact
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

Built React Native ride-hailing navigation app. Uses react-native-maps, react-native-google-places-autocomplete, Redux (navSlice), react-navigation, tailwind-react-native-classnames, and react-native-elements.

NavFavourites component displays 4 preset locations (Home, Work, Business, Game). Pressing a favorite dispatches setDestination action and navigates to RideOptionsCard screen.

Google Places Autocomplete extracts lat/lng via geometry.location and dispatches to Redux store for RideOptionsCard to consume.
