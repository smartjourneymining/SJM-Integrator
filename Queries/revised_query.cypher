// Revised query: Shows touchpoints with Df relations lifted from events
// If event1 -[Df]-> event2, and event1 observes touchpoint1, event2 observes touchpoint2,
// then touchpoint1 -[Df]-> touchpoint2
//
// NOTE: First run create_touchpoint_df.cypher to create Df relationships between touchpoints
// Then this query will show touchpoints with Df relations directly between them

// Revised query: Shows touchpoints with Df relations lifted from events
// If event1 -[Df]-> event2, and event1 observes touchpoint1, event2 observes touchpoint2,
// then touchpoint1 -[Df]-> touchpoint2
//
// NOTE: First run create_touchpoint_df.cypher to create Df relationships between touchpoints
// Then this query will show touchpoints with Df relations directly between them

// Get the journey
MATCH (uj:Journey WHERE uj.journey = 'ID14')

// Get all touchpoints in the journey with their direct relationships
MATCH (uj)-[cnt:Contains]-(tp:Touchpoint)
OPTIONAL MATCH (tp)-[sr:Sender|Receiver]-(en:Entity)
OPTIONAL MATCH (tp)-[cn:Communicated]-(c:Channel)

// Match Df relationships where this touchpoint is the SOURCE (tp -> tp2)
OPTIONAL MATCH (tp)-[tpDfOut:Df {EntityType: 'Journey'}]->(tp2:Touchpoint)
WHERE (uj)-[:Contains]-(tp2)

// Match Df relationships where this touchpoint is the TARGET (tp1 -> tp)
OPTIONAL MATCH (tp1:Touchpoint)-[tpDfIn:Df {EntityType: 'Journey'}]->(tp)
WHERE (uj)-[:Contains]-(tp1)

RETURN 
    tp, 
    tp1,  // Will be null if tp is source, or the source touchpoint if tp is target
    tp2,  // Will be null if tp is target, or the target touchpoint if tp is source
    en, c, uj,
    cnt, sr, cn,
    COALESCE(tpDfOut, tpDfIn) AS tpDf  // Df relation where tp is involved (either direction)
