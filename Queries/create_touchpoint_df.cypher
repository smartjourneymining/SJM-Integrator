// Query to create Df relationships between touchpoints based on Df relations between events
// Run this first to create the Df relationships between touchpoints
// The direction follows the event Df: if e1 -[Df]-> e2, and e1 observes tp1, e2 observes tp2,
// then tp1 -[Df]-> tp2 (from earlier event's touchpoint to later event's touchpoint)


// Now create the Df relationships based on event Df relationships
// IMPORTANT: Only match DIRECT Df relationships (path length 1), not indirect successors
// This ensures we only create Df between touchpoints for directly following events
MATCH (uj:Journey WHERE uj.journey = 'ID14')
// Match only direct Df relationships between events (not paths through multiple Df steps)
MATCH (e1:Event)-[df:Df {EntityType: 'Journey'}]->(e2:Event)
WHERE e1.journey = uj.journey AND e2.journey = uj.journey
MATCH (e1)-[:Observe]->(tp1:Touchpoint)
MATCH (e2)-[:Observe]->(tp2:Touchpoint)
WHERE (uj)-[:Contains]-(tp1)
  AND (uj)-[:Contains]-(tp2)
  AND tp1 <> tp2

// CRITICAL: Get unique touchpoint pairs
// DISTINCT on nodes works by node identity, ensuring we get each unique pair only once
// Even if multiple events observe the same touchpoint, we only process each pair once
WITH DISTINCT tp1, tp2

// Use MERGE to ensure we only create one relationship per touchpoint pair
// MERGE will check if the relationship already exists before creating it
// This prevents duplicates even if the same touchpoint pair appears multiple times
// EntityType is set to 'Journey' for all touchpoint Df relationships
MERGE (tp1)-[tpDf:Df {EntityType: 'Journey'}]->(tp2)
RETURN tp1.Id AS tp1Id, tp2.Id AS tp2Id, tpDf
ORDER BY tp1.Id, tp2.Id
