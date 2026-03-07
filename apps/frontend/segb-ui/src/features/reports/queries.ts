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
          ?activity segb:wasRequestedBy ?human .
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
          ?activity segb:wasRequestedBy ?human .
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
          ?otherActivity segb:wasRequestedBy ?human .
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

SELECT
  ?activity
  (GROUP_CONCAT(DISTINCT ?activityTypeLabel; separator="__SEGB_LINE_BREAK__") AS ?activityType)
  ?usedBy
  ?usedByName
  ?startedAt
  ?model
  ?modelLabel
  ?version
  ?dataset
  ?datasetLabel
  ?score
WHERE {
  ?activity a segb:LoggedActivity ;
            segb:usedMLModel ?model ;
            segb:wasPerformedBy ?usedBy .

  OPTIONAL {
    ?activity a ?activityTypeCandidate .
    FILTER(?activityTypeCandidate != segb:LoggedActivity)
    FILTER(?activityTypeCandidate != prov:Activity)
    OPTIONAL { ?activityTypeCandidate rdfs:label ?activityTypeCandidateLabel }
    BIND(REPLACE(STR(?activityTypeCandidate), "^.*[/#]", "") AS ?activityTypeCandidateId)
    BIND(COALESCE(STR(?activityTypeCandidateLabel), ?activityTypeCandidateId) AS ?activityTypeLabel)
  }
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
GROUP BY ?activity ?usedBy ?usedByName ?startedAt ?model ?modelLabel ?version ?dataset ?datasetLabel ?score
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

  OPTIONAL { ?sharedEvent prov:generatedAtTime ?sharedObservedAt }
  OPTIONAL { ?sourceActivity prov:startedAtTime ?startedAt }
  OPTIONAL { ?sourceActivity prov:endedAtTime ?endedAt }
  BIND(COALESCE(?startedAt, ?endedAt, ?sharedObservedAt) AS ?t)

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

  OPTIONAL { ?sharedEvent prov:generatedAtTime ?sharedObservedAt }
  OPTIONAL { ?sourceActivity prov:startedAtTime ?startedAt }
  OPTIONAL { ?sourceActivity prov:endedAtTime ?endedAt }
  BIND(COALESCE(?startedAt, ?endedAt, ?sharedObservedAt) AS ?t)

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
  {
    SELECT ?robot ?conversationHuman
    WHERE {
      ?pairMessage a schema:Message ;
                   schema:text ?pairText ;
                   prov:wasGeneratedBy ?pairActivity .

      ?pairActivity a segb:LoggedActivity ;
                    segb:wasPerformedBy ?robot .

      OPTIONAL { ?pairMessage schema:sender ?pairSenderBySchema }
      OPTIONAL { ?pairMessage prov:wasAttributedTo ?pairSenderByProv }
      BIND(COALESCE(?pairSenderBySchema, ?pairSenderByProv) AS ?pairSender)

      OPTIONAL {
        ?pairActivity schema:about ?pairSharedEvent .
        ?pairSharedEvent schema:about ?pairHumanByActivity .
        ?pairHumanByActivity a oro:Human .
      }
      OPTIONAL {
        ?pairMessage prov:specializationOf ?pairMessageSharedEvent .
        ?pairMessageSharedEvent schema:about ?pairHumanByMessage .
        ?pairHumanByMessage a oro:Human .
      }
      OPTIONAL {
        ?pairSender a oro:Human .
        BIND(?pairSender AS ?pairHumanBySenderHuman)
      }
      OPTIONAL {
        ?pairSender a prov:Person .
        BIND(?pairSender AS ?pairHumanBySenderPerson)
      }
      OPTIONAL {
        ?robot oro:belongsTo ?pairHumanByOwnership .
        ?pairHumanByOwnership a oro:Human .
      }

      BIND(
        COALESCE(
          ?pairHumanBySenderHuman,
          ?pairHumanBySenderPerson,
          ?pairHumanByMessage,
          ?pairHumanByActivity,
          ?pairHumanByOwnership
        ) AS ?conversationHuman
      )
      FILTER(BOUND(?conversationHuman))

      OPTIONAL { ?pairSender a oro:Human . BIND("human" AS ?pairSenderRoleBySenderHuman) }
      OPTIONAL { ?pairSender a prov:Person . BIND("human" AS ?pairSenderRoleBySenderPerson) }
      OPTIONAL { ?pairSender a oro:Robot . BIND("robot" AS ?pairSenderRoleBySenderRobot) }
      BIND(
        COALESCE(
          ?pairSenderRoleBySenderHuman,
          ?pairSenderRoleBySenderPerson,
          ?pairSenderRoleBySenderRobot,
          IF(BOUND(?pairHumanByMessage), "human", "robot")
        ) AS ?pairSenderRole
      )
    }
    GROUP BY ?robot ?conversationHuman
    HAVING (
      SUM(IF(?pairSenderRole = "human", 1, 0)) > 0 &&
      SUM(IF(?pairSenderRole = "robot", 1, 0)) > 0
    )
  }

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

  OPTIONAL { ?message schema:sender ?senderBySchema }
  OPTIONAL { ?message prov:wasAttributedTo ?senderByProv }
  BIND(COALESCE(?senderBySchema, ?senderByProv) AS ?sender)

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
    ?sender a oro:Human .
    BIND(?sender AS ?humanBySenderHuman)
  }
  OPTIONAL {
    ?sender a prov:Person .
    BIND(?sender AS ?humanBySenderPerson)
  }
  OPTIONAL {
    ?robot oro:belongsTo ?humanByOwnership .
    ?humanByOwnership a oro:Human .
  }

  BIND(COALESCE(?humanBySenderHuman, ?humanBySenderPerson, ?humanByMessage, ?humanByActivity, ?humanByOwnership) AS ?human)
  OPTIONAL { ?human foaf:firstName ?humanName }

  OPTIONAL { ?sender a oro:Human . BIND("human" AS ?senderRoleBySenderHuman) }
  OPTIONAL { ?sender a prov:Person . BIND("human" AS ?senderRoleBySenderPerson) }
  OPTIONAL { ?sender a oro:Robot . BIND("robot" AS ?senderRoleBySenderRobot) }
  BIND(
    COALESCE(
      ?senderRoleBySenderHuman,
      ?senderRoleBySenderPerson,
      ?senderRoleBySenderRobot,
      IF(BOUND(?humanByMessage), "human", "robot")
    ) AS ?senderRole
  )
  BIND(IF(?senderRole = "human", "HumanMessage", IF(?senderRole = "robot", "RobotMessage", "Message")) AS ?messageType)

  BIND("robot" AS ?performedByRole)
  BIND(IF(BOUND(?human), REPLACE(STR(?human), "^.*[/#]", ""), "") AS ?humanId)
  BIND(COALESCE(?humanName, ?humanId, "") AS ?humanLabel)
  BIND(COALESCE(?robotNameRaw, ?robotId, "") AS ?robotLabel)
  FILTER(BOUND(?human))
  FILTER(?human = ?conversationHuman)
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
ORDER BY ?t ?robot
`,
}
