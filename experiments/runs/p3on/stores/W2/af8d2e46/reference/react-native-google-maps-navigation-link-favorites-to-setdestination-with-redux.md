---
name: react-native-google-maps-navigation-link-favorites-to-setdestination-with-redux
abstract: "React Native Google Maps navigation: link favorites to setDestination with redux"
type: reference
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

## Implementation pattern

React Native app with Google Maps navigation, linking favorite locations to navigation actions.

**Libraries used:**
- react-native-maps (MapView, Marker)
- react-redux (useDispatch, useSelector)
- @react-navigation/native (useNavigation)
- react-native-google-places-autocomplete
- tailwind-react-native-classnames

**Pattern:**
1. Store favorite locations in data array with id, icon, location name, destination address
2. Render as FlatList with TouchableOpacity items
3. On press, dispatch setDestination action with destination coordinates/description
4. Navigate to RideOptionsCard screen
5. RideOptionsCard uses useSelector to pull destination from Redux store

**Key dispatch code:**
```javascript
<TouchableOpacity onPress={() => {
  dispatch(setDestination(destination));
  navigation.navigate('RideOptionsCard');
}}>
```

**GooglePlacesAutocomplete config:**
- fetchDetails=true to get geometry.location
- onPress handler dispatches setDestination with {location: details.geometry.location, description: data.description}
- Uses GOOGLE_MAPS_APIKEY from .env file

**Flow:** User presses favorite → dispatch setDestination → navigate to RideOptionsCard → useSelector retrieves destination from store
