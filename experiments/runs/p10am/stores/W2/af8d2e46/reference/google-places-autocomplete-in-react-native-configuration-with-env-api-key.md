---
name: google-places-autocomplete-in-react-native-configuration-with-env-api-key
abstract: "Google Places Autocomplete in React Native: configuration with .env API key"
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

react-native-google-places-autocomplete setup:

Import from environment: import {GOOGLE_MAPS_APIKEY} from "@env";

Configure component with:
- placeholder: location search prompt
- fetchDetails: true (enables geometry extraction)
- enablePoweredByContainer: false (hides Google branding)
- minLength: 2 (search after 2 chars)
- returnKeyType: search
- query object with key: GOOGLE_MAPS_APIKEY and language: en

Details callback (onPress) receives two arguments:
- data: contains description (user-friendly location name)
- details: contains geometry.location with latitude/longitude coordinates

Use this pattern for any location autocomplete in React Native apps.
