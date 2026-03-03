export const REPORT_EXTREME_EMOTION_THRESHOLD = 0.75
const EXTREME_THRESHOLD_LITERAL = REPORT_EXTREME_EMOTION_THRESHOLD.toFixed(2)

export const reportQueries = {
  participantsHumans: `
PREFIX segb: <http://www.gsi.upm.es/ontologies/segb/ns#>
PREFIX oro: <http://kb.openrobots.org#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX schema: <http://schema.org/>

SELECT
  ?participant
  (GROUP_CONCAT(DISTINCT ?robotDisplay; separator="__SEGB_LINE_BREAK__") AS ?interactedRobots)
WHERE {
  ?activity a segb:LoggedActivity ;
            segb:wasPerformedBy ?robot .
  ?robot a oro:Robot .
  OPTIONAL { ?robot schema:name ?robotNameRaw }
  BIND(REPLACE(STR(?robot), "^.*[/#]", "") AS ?robotId)
  BIND(COALESCE(?robotNameRaw, ?robotId) AS ?robotDisplay)

  {
    ?activity schema:about ?sharedEvent .
    ?sharedEvent schema:about ?human .
  }
  UNION
  {
    ?activity segb:wasRequestedBy ?human .
  }
  UNION
  {
    ?robot oro:belongsTo ?human .
  }

  ?human a oro:Human .
  OPTIONAL { ?human foaf:firstName ?humanName }
  BIND(COALESCE(?humanName, STR(?human)) AS ?participant)
}
GROUP BY ?participant
ORDER BY ?participant
`,

  participantsRobots: `
PREFIX segb: <http://www.gsi.upm.es/ontologies/segb/ns#>
PREFIX oro: <http://kb.openrobots.org#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX schema: <http://schema.org/>

SELECT
  ?participant
  (GROUP_CONCAT(DISTINCT ?interactedHuman; separator="__SEGB_LINE_BREAK__") AS ?interactedHumans)
  (GROUP_CONCAT(DISTINCT ?interactedRobot; separator="__SEGB_LINE_BREAK__") AS ?interactedRobots)
WHERE {
  ?robot a oro:Robot .
  OPTIONAL { ?robot schema:name ?robotNameRaw }
  BIND(REPLACE(STR(?robot), "^.*[/#]", "") AS ?robotId)
  BIND(COALESCE(?robotNameRaw, ?robotId) AS ?participant)

  OPTIONAL {
    {
      SELECT DISTINCT ?robot ?interactedHuman
      WHERE {
        ?activity a segb:LoggedActivity ;
                  segb:wasPerformedBy ?robot .

        {
          ?activity schema:about ?sharedEvent .
          ?sharedEvent schema:about ?human .
        }
        UNION
        {
          ?robot oro:belongsTo ?human .
        }

        ?human a oro:Human .
        OPTIONAL { ?human foaf:firstName ?humanName }
        BIND(COALESCE(?humanName, STR(?human)) AS ?interactedHuman)
      }
    }
  }

  OPTIONAL {
    {
      SELECT DISTINCT ?robot ?interactedRobot
      WHERE {
        ?activity a segb:LoggedActivity ;
                  segb:wasPerformedBy ?robot .

        {
          ?activity schema:about ?sharedEvent .
          ?sharedEvent schema:about ?human .
        }
        UNION
        {
          ?robot oro:belongsTo ?human .
        }

        ?human a oro:Human .

        ?otherActivity a segb:LoggedActivity ;
                       segb:wasPerformedBy ?otherRobot .
        FILTER (?otherRobot != ?robot)

        {
          ?otherActivity schema:about ?otherSharedEvent .
          ?otherSharedEvent schema:about ?human .
        }
        UNION
        {
          ?otherRobot oro:belongsTo ?human .
        }

        OPTIONAL { ?otherRobot schema:name ?otherRobotNameRaw }
        BIND(REPLACE(STR(?otherRobot), "^.*[/#]", "") AS ?otherRobotId)
        BIND(COALESCE(?otherRobotNameRaw, ?otherRobotId) AS ?interactedRobot)
      }
    }
  }
}
GROUP BY ?participant
ORDER BY ?participant
`,

  mlUsage: `
PREFIX segb: <http://www.gsi.upm.es/ontologies/segb/ns#>
PREFIX mls: <http://www.w3.org/ns/mls#>
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX oro: <http://kb.openrobots.org#>
PREFIX prov: <http://www.w3.org/ns/prov#>

SELECT ?activity ?activityType ?usedBy ?usedByName ?startedAt ?model ?modelLabel ?version ?dataset ?datasetLabel ?score
WHERE {
  ?activity a segb:LoggedActivity ;
            segb:usedMLModel ?model ;
            segb:wasPerformedBy ?usedBy .

  OPTIONAL { ?activity a ?activityType . FILTER(?activityType != segb:LoggedActivity) }
  OPTIONAL { ?usedBy schema:name ?usedByNameRaw }
  BIND(REPLACE(STR(?usedBy), "^.*[/#]", "") AS ?usedById)
  BIND(COALESCE(?usedByNameRaw, ?usedById) AS ?usedByName)
  OPTIONAL { ?activity prov:startedAtTime ?startedAt }

  OPTIONAL { ?model rdfs:label ?modelLabel }
  OPTIONAL { ?model schema:version ?version }

  OPTIONAL {
    ?run a mls:Run ;
         mls:hasOutput ?model .
    OPTIONAL {
      ?run mls:hasInput ?dataset .
      OPTIONAL { ?dataset rdfs:label ?datasetLabel }
    }
    OPTIONAL {
      ?run mls:hasOutput ?eval .
      ?eval a mls:ModelEvaluation ;
            mls:hasValue ?score .
    }
  }
}
ORDER BY ?startedAt ?activity
`,

  emotionTimeline: `
PREFIX onyx: <http://www.gsi.upm.es/ontologies/onyx/ns#>
PREFIX segb: <http://www.gsi.upm.es/ontologies/segb/ns#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX oa: <http://www.w3.org/ns/oa#>
PREFIX oro: <http://kb.openrobots.org#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>

SELECT DISTINCT
  ?t
  ?sourceActivity
  ?performedBy
  ?performedByLabel
  ?performedByType
  ?targetEntity
  ?targetType
  ?targetLabel
  ?category
  ?intensity
  ?confidence
WHERE {
  ?sourceActivity a onyx:EmotionAnalysis ;
                 a segb:LoggedActivity ;
                 schema:about ?sharedEvent .
  OPTIONAL { ?sourceActivity segb:wasPerformedBy ?performedBy }
  {
    ?sourceActivity segb:producedEntityResult ?emotionContainer .
  }
  UNION
  {
    ?sourceActivity prov:generated ?emotionContainer .
    FILTER NOT EXISTS { ?sourceActivity segb:producedEntityResult ?emotionContainer }
  }
  ?sharedEvent schema:about ?targetEntity .

  OPTIONAL { ?sharedEvent prov:generatedAtTime ?sharedObservedAt }
  OPTIONAL { ?sourceActivity prov:startedAtTime ?startedAt }
  OPTIONAL { ?sourceActivity prov:endedAtTime ?endedAt }
  BIND(COALESCE(?sharedObservedAt, ?startedAt, ?endedAt) AS ?t)

  ?emotionContainer onyx:hasEmotion ?emotion .
  ?emotion onyx:hasEmotionCategory ?category ;
           onyx:hasEmotionIntensity ?intensity .
  OPTIONAL { ?emotion onyx:algorithmConfidence ?confidence }

  ?emotionContainer oa:hasTarget ?targetEntity .
  {
    SELECT ?emotionContainer (COUNT(DISTINCT ?containerTarget) AS ?targetCount)
    WHERE {
      ?emotionContainer oa:hasTarget ?containerTarget .
    }
    GROUP BY ?emotionContainer
  }
  FILTER(?targetCount = 1)

  OPTIONAL { ?targetEntity foaf:firstName ?personName }
  OPTIONAL { ?targetEntity schema:name ?robotName }
  OPTIONAL { ?targetEntity rdfs:label ?entityLabel }
  BIND(REPLACE(STR(?targetEntity), "^.*[/#]", "") AS ?targetEntityId)
  BIND(COALESCE(?personName, ?robotName, ?entityLabel, ?targetEntityId) AS ?targetLabel)

  OPTIONAL { ?performedBy foaf:firstName ?performedByPersonName }
  OPTIONAL { ?performedBy schema:name ?performedByRobotName }
  OPTIONAL { ?performedBy rdfs:label ?performedByEntityLabel }
  BIND(IF(BOUND(?performedBy), REPLACE(STR(?performedBy), "^.*[/#]", ""), "") AS ?performedById)
  BIND(COALESCE(?performedByPersonName, ?performedByRobotName, ?performedByEntityLabel, ?performedById) AS ?performedByLabel)

  OPTIONAL { ?performedBy a oro:Robot . BIND("robot" AS ?performedByTypeRobot) }
  OPTIONAL { ?performedBy a oro:Human . BIND("human" AS ?performedByTypeHuman) }
  OPTIONAL { ?performedBy a prov:Person . BIND("human" AS ?performedByTypePerson) }
  BIND(COALESCE(?performedByTypeRobot, ?performedByTypeHuman, ?performedByTypePerson, "entity") AS ?performedByType)

  OPTIONAL { ?targetEntity a oro:Robot . BIND("robot" AS ?targetTypeRobot) }
  OPTIONAL { ?targetEntity a oro:Human . BIND("human" AS ?targetTypeHuman) }
  OPTIONAL { ?targetEntity a prov:Person . BIND("human" AS ?targetTypePerson) }
  BIND(COALESCE(?targetTypeRobot, ?targetTypeHuman, ?targetTypePerson, "entity") AS ?targetType)
  FILTER(?targetType = "human" || ?targetType = "robot")
}
ORDER BY ?t DESC(?intensity)
`,

  extremeEmotion: `
PREFIX onyx: <http://www.gsi.upm.es/ontologies/onyx/ns#>
PREFIX segb: <http://www.gsi.upm.es/ontologies/segb/ns#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX oa: <http://www.w3.org/ns/oa#>
PREFIX oro: <http://kb.openrobots.org#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?t ?sourceActivity ?targetEntity ?targetType ?targetLabel ?category ?intensity ?confidence
WHERE {
  ?sourceActivity a onyx:EmotionAnalysis ;
                 a segb:LoggedActivity ;
                 schema:about ?sharedEvent .
  {
    ?sourceActivity segb:producedEntityResult ?emotionContainer .
  }
  UNION
  {
    ?sourceActivity prov:generated ?emotionContainer .
    FILTER NOT EXISTS { ?sourceActivity segb:producedEntityResult ?emotionContainer }
  }
  ?sharedEvent schema:about ?targetEntity .

  OPTIONAL { ?sharedEvent prov:generatedAtTime ?sharedObservedAt }
  OPTIONAL { ?sourceActivity prov:startedAtTime ?startedAt }
  OPTIONAL { ?sourceActivity prov:endedAtTime ?endedAt }
  BIND(COALESCE(?sharedObservedAt, ?startedAt, ?endedAt) AS ?t)

  ?emotionContainer onyx:hasEmotion ?emotion .
  ?emotion onyx:hasEmotionCategory ?category ;
           onyx:hasEmotionIntensity ?intensity .
  OPTIONAL { ?emotion onyx:algorithmConfidence ?confidence }

  ?emotionContainer oa:hasTarget ?targetEntity .
  {
    SELECT ?emotionContainer (COUNT(DISTINCT ?containerTarget) AS ?targetCount)
    WHERE {
      ?emotionContainer oa:hasTarget ?containerTarget .
    }
    GROUP BY ?emotionContainer
  }
  FILTER(?targetCount = 1)

  OPTIONAL { ?targetEntity a oro:Human . BIND("human" AS ?targetTypeHuman) }
  OPTIONAL { ?targetEntity a prov:Person . BIND("human" AS ?targetTypePerson) }
  BIND(COALESCE(?targetTypeHuman, ?targetTypePerson, "entity") AS ?targetType)
  FILTER(?targetType = "human")

  OPTIONAL { ?targetEntity foaf:firstName ?personName }
  OPTIONAL { ?targetEntity rdfs:label ?entityLabel }
  BIND(REPLACE(STR(?targetEntity), "^.*[/#]", "") AS ?targetEntityId)
  BIND(COALESCE(?personName, ?entityLabel, ?targetEntityId) AS ?targetLabel)

  BIND(xsd:double(STR(?intensity)) AS ?intensityValue)
  FILTER(BOUND(?intensityValue))
  FILTER(?intensityValue >= ${EXTREME_THRESHOLD_LITERAL})
}
ORDER BY DESC(?intensityValue)
`,

  conversationHistory: `
PREFIX segb: <http://www.gsi.upm.es/ontologies/segb/ns#>
PREFIX oro: <http://kb.openrobots.org#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX schema: <http://schema.org/>
PREFIX prov: <http://www.w3.org/ns/prov#>

SELECT
  ?message
  ?activity
  ?t
  ?human
  ?humanLabel
  ?robot
  ?robotLabel
  ?text
  ?messageType
  ?senderRole
  ?performedByRole
WHERE {
  ?message a schema:Message ;
           schema:text ?text ;
           prov:wasGeneratedBy ?activity .

  ?activity a segb:LoggedActivity ;
            segb:wasPerformedBy ?robot .

  ?robot a oro:Robot .
  OPTIONAL { ?robot schema:name ?robotNameRaw }
  BIND(REPLACE(STR(?robot), "^.*[/#]", "") AS ?robotId)

  OPTIONAL { ?activity prov:startedAtTime ?startedAt }
  OPTIONAL { ?activity prov:endedAtTime ?endedAt }
  BIND(COALESCE(?startedAt, ?endedAt) AS ?t)

  OPTIONAL {
    ?activity schema:about ?sharedEvent .
    ?sharedEvent schema:about ?humanByActivity .
    ?humanByActivity a oro:Human .
  }
  OPTIONAL {
    ?message prov:specializationOf ?messageSharedEvent .
    ?messageSharedEvent schema:about ?humanByMessage .
    ?humanByMessage a oro:Human .
  }
  OPTIONAL {
    ?robot oro:belongsTo ?humanByOwnership .
    ?humanByOwnership a oro:Human .
  }

  BIND(COALESCE(?humanByMessage, ?humanByActivity, ?humanByOwnership) AS ?human)
  OPTIONAL { ?human foaf:firstName ?humanName }

  BIND(IF(BOUND(?humanByMessage), "human", "robot") AS ?senderRole)
  BIND(IF(?senderRole = "human", "HumanMessage", "RobotMessage") AS ?messageType)

  BIND("robot" AS ?performedByRole)
  BIND(IF(BOUND(?human), REPLACE(STR(?human), "^.*[/#]", ""), "") AS ?humanId)
  BIND(COALESCE(?humanName, ?humanId, "") AS ?humanLabel)
  BIND(COALESCE(?robotNameRaw, ?robotId, "") AS ?robotLabel)
  FILTER(BOUND(?human))
}
ORDER BY ?humanLabel ?robotLabel ?t ?message
`,

  robotState: `
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX schema: <http://schema.org/>
PREFIX oro: <http://kb.openrobots.org#>

SELECT ?robot ?robotName ?t ?location
WHERE {
  ?state a prov:Entity ;
         prov:wasAttributedTo ?robot ;
         prov:atLocation ?location .
  ?robot a oro:Robot .
  OPTIONAL { ?robot schema:name ?robotNameRaw }
  BIND(REPLACE(STR(?robot), "^.*[/#]", "") AS ?robotId)
  BIND(COALESCE(?robotNameRaw, ?robotId) AS ?robotName)
  OPTIONAL { ?state prov:generatedAtTime ?generatedAt }
  OPTIONAL { ?state prov:startedAtTime ?stateStartedAt }
  OPTIONAL { ?state prov:endedAtTime ?stateEndedAt }
  BIND(COALESCE(?generatedAt, ?stateStartedAt, ?stateEndedAt, "") AS ?t)
}
ORDER BY ?robot ?t
`,
}
