package com.tukorea.echomind.models

import java.io.Serializable

data class MatchCandidate(
    val profile: PersonalityProfile,
    var matchScore: Int = 0,
    var similarityScore: Double = 0.0,
    var chemistryScore: Double = 0.0,
    var activityScore: Double = 0.0,
    val relativeTraits: List<RelativeTrait> = emptyList()
) : Serializable

data class RelativeTrait(
    val name: String,
    val label: String, // "높음", "낮음"
    val color: String  // UI용 색상 코드
) : Serializable
