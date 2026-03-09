export const REPORT_EXTREME_EMOTION_THRESHOLD = 0.75
const EXTREME_THRESHOLD_LITERAL = REPORT_EXTREME_EMOTION_THRESHOLD.toFixed(2)

const entityDisplayBinding = (variableName: string, outputName: string) => `
  OPTIONAL { ${variableName} foaf:firstName ?${outputName}FirstName }
  OPTIONAL { ${variableName} schema:name ?${outputName}SchemaName }
  OPTIONAL { ${variableName} rdfs:label ?${outputName}RdfsLabel }
  BIND(REPLACE(STR(${variableName}), "^.*[/#]", "") AS ?${outputName}Id)
  BIND(COALESCE(?${outputName}FirstName, ?${outputName}SchemaName, ?${outputName}RdfsLabel, ?${outputName}Id) AS ?${outputName})
`

const humanTypePattern = (variableName: string) => `{
  ${variableName} a oro:Human .
}
UNION
{
  ${variableName} a foaf:Person .
}
UNION
{
  ${variableName} a prov:Person .
}`

const humanRoleBindings = (variableName: string, outputName: string) => `
  OPTIONAL { ${variableName} a oro:Human . BIND("human" AS ?${outputName}OroHuman) }
  OPTIONAL { ${variableName} a foaf:Person . BIND("human" AS ?${outputName}FoafPerson) }
  OPTIONAL { ${variableName} a prov:Person . BIND("human" AS ?${outputName}ProvPerson) }
`

const linkedHumanPattern = (
  activityName: string,
  robotName: string,
  humanName: string,
  sharedEventName: string,
) => `{
  ${activityName} schema:about ${sharedEventName} .
  ${sharedEventName} schema:about ${humanName} .
}
UNION
{
  ${activityName} segb:wasRequestedBy ${humanName} .
}
UNION
{
  ${robotName} oro:belongsTo ${humanName} .
}
UNION
{
  ${activityName} oro:hasSpeaker ${robotName} ;
                 oro:hasListener ${humanName} .
}
UNION
{
  ${activityName} oro:hasSpeaker ${humanName} ;
                 oro:hasListener ${robotName} .
}`

export const reportQueries = {
  participantsHumans: `
PREFIX segb: <http://www.gsi.upm.es/ontologies/segb/ns#>
PREFIX oro: <http://kb.openrobots.org#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>

SELECT
  ?participant
  (GROUP_CONCAT(DISTINCT ?robotDisplay; separator="__SEGB_LINE_BREAK__") AS ?interactedRobots)
WHERE {
  ${humanTypePattern('?human')}
  FILTER NOT EXISTS { ?human a oro:Robot . }
  ${entityDisplayBinding('?human', 'participant')}

  OPTIONAL {
    ?activity a segb:LoggedActivity ;
              segb:wasPerformedBy ?robot .
    ?robot a oro:Robot .
    ${entityDisplayBinding('?robot', 'robotDisplay')}
    ${linkedHumanPattern('?activity', '?robot', '?human', '?sharedEvent')}
  }
}
GROUP BY ?participant
ORDER BY ?participant
`,

  participantsRobots: `
PREFIX segb: <http://www.gsi.upm.es/ontologies/segb/ns#>
PREFIX oro: <http://kb.openrobots.org#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>

SELECT
  ?participant
  (GROUP_CONCAT(DISTINCT ?interactedHuman; separator="__SEGB_LINE_BREAK__") AS ?interactedHumans)
  (GROUP_CONCAT(DISTINCT ?interactedRobot; separator="__SEGB_LINE_BREAK__") AS ?interactedRobots)
WHERE {
  ?robot a oro:Robot .
  ${entityDisplayBinding('?robot', 'participant')}

  OPTIONAL {
    {
      SELECT DISTINCT ?robot ?interactedHuman
      WHERE {
        ?activity a segb:LoggedActivity ;
                  segb:wasPerformedBy ?robot .
        ${linkedHumanPattern('?activity', '?robot', '?human', '?sharedEvent')}
        ${humanTypePattern('?human')}
        FILTER NOT EXISTS { ?human a oro:Robot . }
        ${entityDisplayBinding('?human', 'interactedHuman')}
      }
    }
  }

  OPTIONAL {
    {
      SELECT DISTINCT ?robot ?interactedRobot
      WHERE {
        ?activity a segb:LoggedActivity ;
                  segb:wasPerformedBy ?robot .
        ${linkedHumanPattern('?activity', '?robot', '?human', '?sharedEvent')}
        ${humanTypePattern('?human')}
        FILTER NOT EXISTS { ?human a oro:Robot . }

        ?otherActivity a segb:LoggedActivity ;
                       segb:wasPerformedBy ?otherRobot .
        FILTER (?otherRobot != ?robot)
        ${linkedHumanPattern('?otherActivity', '?otherRobot', '?human', '?otherSharedEvent')}
        ${entityDisplayBinding('?otherRobot', 'interactedRobot')}
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
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

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
  ${entityDisplayBinding('?usedBy', 'usedByName')}
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

  ${entityDisplayBinding('?targetEntity', 'targetLabel')}

  ${entityDisplayBinding('?performedBy', 'performedByLabel')}

  OPTIONAL { ?performedBy a oro:Robot . BIND("robot" AS ?performedByTypeRobot) }
  ${humanRoleBindings('?performedBy', 'performedByType')}
  BIND(
    COALESCE(
      ?performedByTypeRobot,
      ?performedByTypeOroHuman,
      ?performedByTypeFoafPerson,
      ?performedByTypeProvPerson,
      "entity"
    ) AS ?performedByType
  )

  OPTIONAL { ?targetEntity a oro:Robot . BIND("robot" AS ?targetTypeRobot) }
  ${humanRoleBindings('?targetEntity', 'targetType')}
  BIND(
    COALESCE(
      ?targetTypeRobot,
      ?targetTypeOroHuman,
      ?targetTypeFoafPerson,
      ?targetTypeProvPerson,
      "entity"
    ) AS ?targetType
  )
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

  ${humanRoleBindings('?targetEntity', 'targetType')}
  BIND(COALESCE(?targetTypeOroHuman, ?targetTypeFoafPerson, ?targetTypeProvPerson, "entity") AS ?targetType)
  FILTER(?targetType = "human")

  ${entityDisplayBinding('?targetEntity', 'targetLabel')}

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
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

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
      OPTIONAL { ?pairActivity oro:hasSpeaker ?pairSpeaker }
      OPTIONAL { ?pairActivity oro:hasListener ?pairListener }
      BIND(COALESCE(?pairSenderBySchema, ?pairSenderByProv, ?pairSpeaker) AS ?pairSender)

      OPTIONAL {
        ?pairActivity schema:about ?pairSharedEvent .
        ?pairSharedEvent schema:about ?pairHumanByActivity .
        ${humanTypePattern('?pairHumanByActivity')}
      }
      OPTIONAL {
        ?pairMessage prov:specializationOf ?pairMessageSharedEvent .
        ?pairMessageSharedEvent schema:about ?pairHumanByMessage .
        ${humanTypePattern('?pairHumanByMessage')}
      }
      OPTIONAL {
        ${humanTypePattern('?pairSpeaker')}
        BIND(?pairSpeaker AS ?pairHumanBySpeaker)
      }
      OPTIONAL {
        ${humanTypePattern('?pairListener')}
        BIND(?pairListener AS ?pairHumanByListener)
      }
      OPTIONAL {
        ?robot oro:belongsTo ?pairHumanByOwnership .
        ${humanTypePattern('?pairHumanByOwnership')}
      }

      BIND(
        COALESCE(
          ?pairHumanBySpeaker,
          ?pairHumanByListener,
          ?pairHumanByMessage,
          ?pairHumanByActivity,
          ?pairHumanByOwnership
        ) AS ?conversationHuman
      )
      FILTER(BOUND(?conversationHuman))

      ${humanRoleBindings('?pairSender', 'pairSenderRoleBySender')}
      OPTIONAL { ?pairSender a oro:Robot . BIND("robot" AS ?pairSenderRoleBySenderRobot) }
      BIND(
        COALESCE(
          ?pairSenderRoleBySenderOroHuman,
          ?pairSenderRoleBySenderFoafPerson,
          ?pairSenderRoleBySenderProvPerson,
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
  ${entityDisplayBinding('?robot', 'robotLabel')}

  OPTIONAL { ?activity prov:startedAtTime ?startedAt }
  OPTIONAL { ?activity prov:endedAtTime ?endedAt }
  BIND(COALESCE(?startedAt, ?endedAt) AS ?t)

  OPTIONAL { ?message schema:sender ?senderBySchema }
  OPTIONAL { ?message prov:wasAttributedTo ?senderByProv }
  OPTIONAL { ?activity oro:hasSpeaker ?speaker }
  OPTIONAL { ?activity oro:hasListener ?listener }
  BIND(COALESCE(?senderBySchema, ?senderByProv, ?speaker) AS ?sender)

  OPTIONAL {
    ?activity schema:about ?sharedEvent .
    ?sharedEvent schema:about ?humanByActivity .
    ${humanTypePattern('?humanByActivity')}
  }
  OPTIONAL {
    ?message prov:specializationOf ?messageSharedEvent .
    ?messageSharedEvent schema:about ?humanByMessage .
    ${humanTypePattern('?humanByMessage')}
  }
  OPTIONAL {
    ${humanTypePattern('?speaker')}
    BIND(?speaker AS ?humanBySpeaker)
  }
  OPTIONAL {
    ${humanTypePattern('?listener')}
    BIND(?listener AS ?humanByListener)
  }
  OPTIONAL {
    ?robot oro:belongsTo ?humanByOwnership .
    ${humanTypePattern('?humanByOwnership')}
  }

  BIND(COALESCE(?humanBySpeaker, ?humanByListener, ?humanByMessage, ?humanByActivity, ?humanByOwnership) AS ?human)
  ${entityDisplayBinding('?human', 'humanLabel')}

  ${humanRoleBindings('?sender', 'senderRoleBySender')}
  OPTIONAL { ?sender a oro:Robot . BIND("robot" AS ?senderRoleBySenderRobot) }
  BIND(
    COALESCE(
      ?senderRoleBySenderOroHuman,
      ?senderRoleBySenderFoafPerson,
      ?senderRoleBySenderProvPerson,
      ?senderRoleBySenderRobot,
      IF(BOUND(?humanByMessage), "human", "robot")
    ) AS ?senderRole
  )
  BIND(IF(?senderRole = "human", "HumanMessage", IF(?senderRole = "robot", "RobotMessage", "Message")) AS ?messageType)

  BIND("robot" AS ?performedByRole)
  FILTER(BOUND(?human))
  FILTER(?human = ?conversationHuman)
}
ORDER BY ?humanLabel ?robotLabel ?t ?message
`,

  robotState: `
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX schema: <http://schema.org/>
PREFIX oro: <http://kb.openrobots.org#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?robot ?robotName ?t ?location
WHERE {
  ?state a prov:Entity ;
         prov:wasAttributedTo ?robot ;
         prov:atLocation ?location .
  ?robot a oro:Robot .
  ${entityDisplayBinding('?robot', 'robotName')}
  OPTIONAL { ?state prov:generatedAtTime ?generatedAt }
  OPTIONAL { ?state prov:startedAtTime ?stateStartedAt }
  OPTIONAL { ?state prov:endedAtTime ?stateEndedAt }
  BIND(COALESCE(?generatedAt, ?stateStartedAt, ?stateEndedAt, "") AS ?t)
}
ORDER BY ?t ?robot
`,
}
