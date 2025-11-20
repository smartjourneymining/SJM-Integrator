// Query to delete all Df relationships between touchpoints in a journey
// Run this before create_touchpoint_df.cypher to clean up existing relationships

MATCH (uj:Journey WHERE uj.journey = 'ID14')
MATCH (uj)-[:Contains]-(tp1:Touchpoint)-[df:Df]-(tp2:Touchpoint)
WHERE (uj)-[:Contains]-(tp2)
DELETE df
RETURN COUNT(df) AS deletedRelationships

