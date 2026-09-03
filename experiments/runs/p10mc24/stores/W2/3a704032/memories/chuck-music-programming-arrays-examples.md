---
created: 2026-09-02T21:27:39.549368738Z
updated: 2026-09-02T21:27:39.549368738Z
weight: 1.0
last_accessed: 2026-09-02T21:27:39.549368738Z
access_count: 0
pinned: false
links: []
abstract: May 2023 — ChucK examples for music. Array syntax, melody generation with Note.freq(), chord progression with 2D arrays
---

## ChucK Music Programming Examples

### Array Declaration and Syntax
ChucK arrays are zero-indexed with fixed size at declaration. Use `.cap()` method to get number of elements.

```chuck
// Declaring an array of integers
int myArray[5];
myArray[0] = 5;

// Declaring and initializing array
float myFloatArray[] = [1.5, 2.6, 3.7];

// Accessing elements
<<<"Element 1 is ", myFloatArray[0]>>>;

// Iterating with for loop
for (int i = 0; i < myArray.cap(); i++) {
    <<<"Element ", i, " is ", myArray[i]>>>;
}
```

### Melody Example
```chuck
int melody[] = [60, 62, 64, 65, 67, 69, 71, 72];

while (true) {
    for (int i = 0; i < melody.cap(); i++) {
        play(Note.freq(melody[i]));
        1::second => now;
    }
}
```

### Chord Progression Example
```chuck
int chords[][] = [
    [60, 64, 67], // C major
    [57, 60, 64], // F major
    [55, 59, 62], // G major
    [62, 65, 69], // A minor
];

while (true) {
    for (int i = 0; i < chords.cap(); i++) {
        for (int j = 0; j < chords[i].cap(); j++) {
            play(Note.freq(chords[i][j]), 1::second);
        }
        2::second => now;
    }
}
```