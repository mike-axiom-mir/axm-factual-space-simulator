# Factual Ship Systems Blueprint v1

## Purpose

The first ship is now represented as an interconnected spacecraft system rather than a collection of independent rooms.

The blueprint contains 22 systems:

1. Primary structure and pressure hull
2. Micrometeoroid and debris protection
3. Electrical power generation
4. Energy storage
5. Power conversion and distribution
6. Thermal control
7. Main propulsion
8. Reaction and attitude-control effectors
9. Guidance, navigation, and control
10. Avionics, command, and data handling
11. Communications and tracking
12. Atmosphere control and revitalization
13. Water recovery and waste management
14. Fire and emergency response
15. Radiation monitoring and shelter
16. Docking, airlock, and EVA support
17. Robotics and probe operations
18. External navigation, environment, and science sensors
19. Science payload and analysis
20. Crew health and medical support
21. Logistics, maintenance, spares, and fabrication
22. Integrated fault management

## Truth classes

Every numeric or categorical parameter is one of:

- `catalog_fact`
- `derived`
- `simulation_design_assumption`
- `unknown`

The first ship is not presented as flight-certified. Its complete mass, verified delta-v, propulsion performance, structural load envelope, and validated mission duration remain unknown until a real integrated design and source package exists.

## System behavior

Power, heat, pressure, water, atmosphere, communications delay, navigation uncertainty, radiation exposure, maintenance, faults, and encounters are coupled.

A damaged array can reduce power. Reduced power can cause load shedding. Load shedding may protect life support while reducing science, communications, or robotics. A thermal fault can force attitude changes that affect generation and antenna pointing. These consequences are stateful and replayable.
