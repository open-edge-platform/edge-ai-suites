Trigger condition: A "collision" is counted when jaywalking is detected simultaneously with vehicles present in the NOPED (no-pedestrian) region.

Step-by-step logic:

  1. Extract counts from the SceneScape region event for the current region:
       pedestrian_noped_count = number of pedestrians in this region
       vehicle_noped_count = number of vehicles in this region

  2. Jaywalking check: jaywalking_detected = true only when:
      The region is "NOPED" (the no-pedestrian zone), AND
      pedestrian_noped_count > 0 (at least one pedestrian is in that zone)
     
  3. Collision count:
      If jaywalking is detected → collision_count = vehicle_noped_count (every vehicle in the zone counts as a potential collision)
      If no jaywalking → collision_count = 0

  4. Publish a collision_events_2 measurement to InfluxDB with:
      count: the collision count
      trigger: 1 if any collisions, 0 otherwise
      Tags: location=Anthem, region=NOPED, object=vehicle

  5. Grafana dashboard shows a "Vehicle Collisions" panel querying the collision_events_2 measurement