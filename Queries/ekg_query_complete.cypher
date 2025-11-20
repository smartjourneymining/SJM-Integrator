MATCH (uj : Journey WHERE uj.journey = 'ID14')
    -[cnt:Contains]-(tp:Touchpoint)
    -[sr:Sender|Receiver]-(en: Entity) 
MATCH (tp:Touchpoint)-[obs:Observe]-(e:Event)
MATCH (e:Event)
    -[df:Df {EntityType: 'Journey'}]
    -(e2:Event) 
OPTIONAL MATCH (e:Event)-[corr:Corr]-(en)
OPTIONAL MATCH (tp:Touchpoint)-[cn:Communicated]-(c:Channel)
RETURN *