// Query to create Df relationships between touchpoints based on Df relations between events
// Run this after delete_touchpoint_df.cypher to create the Df relationships between touchpoints
// The direction follows the event Df: if e1 -[Df]-> e2, and e1 observes tp1, e2 observes tp2,
// then tp1 -[Df]-> tp2 (from earlier event's touchpoint to later event's touchpoint)
//
// IMPORTANT: Only creates ONE Df relationship per unique touchpoint pair, even if multiple
// event pairs connect the same touchpoints

// Match the journey
MATCH (uj:Journey WHERE uj.journey = 'ID14')

// Match only direct Df relationships between events (not paths through multiple Df steps)
// IMPORTANT: Only match DIRECT Df relationships (path length 1), not indirect successors
// This ensures we only create Df between touchpoints for directly following events
MATCH (e1:Event)-[df:Df {EntityType: 'Journey'}]->(e2:Event)
WHERE e1.journey = uj.journey AND e2.journey = uj.journey

// Match the touchpoints observed by these events
MATCH (e1)-[:Observe]->(tp1:Touchpoint)
MATCH (e2)-[:Observe]->(tp2:Touchpoint)
WHERE (uj)-[:Contains]-(tp1)
  AND (uj)-[:Contains]-(tp2)
  AND tp1 <> tp2

// CRITICAL: Collect all unique touchpoint pairs first
// Use COLLECT to gather all pairs, then UNWIND to process each unique pair once
WITH tp1, tp2, COLLECT(DISTINCT df.EntityType)[0] AS entityType
WITH DISTINCT tp1, tp2, entityType

// Use MERGE to ensure we only create one relationship per touchpoint pair
// MERGE will check if the relationship already exists before creating it
MERGE (tp1)-[tpDf:Df {EntityType: entityType}]->(tp2)
RETURN tp1, tp2, tpDf
ORDER BY tp1.Id, tp2.Id
