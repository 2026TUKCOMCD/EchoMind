package com.tukorea.echomind.models

import java.io.Serializable

data class PersonalityProfile(
    val userId: String? = "unknown",
    val name: String? = "unknown",
    val summary: SummaryData? = null,
    val mbti: MbtiData? = null,
    val big5: Big5Data? = null,
    val socionics: SocionicsData? = null,
    val caveats: List<String>? = emptyList(),
    val lineCount: Int = 0
) : Serializable

data class SummaryData(
    val one_paragraph: String? = "",
    val communication_style_bullets: List<String>? = emptyList()
) : Serializable

data class MbtiData(
    val type: String? = "",
    val confidence: Double = 0.0,
    val reasons: List<String>? = emptyList()
) : Serializable

data class Big5Data(
    val scores_0_100: Big5Scores? = null,
    val confidence: Double = 0.0,
    val reasons: List<String>? = emptyList()
) : Serializable

data class Big5Scores(
    val openness: Double = 50.0,
    val conscientiousness: Double = 50.0,
    val extraversion: Double = 50.0,
    val agreeableness: Double = 50.0,
    val neuroticism: Double = 50.0
) : Serializable

data class SocionicsData(
    val type: String? = "",
    val confidence: Double = 0.0,
    val reasons: List<String>? = emptyList()
) : Serializable
