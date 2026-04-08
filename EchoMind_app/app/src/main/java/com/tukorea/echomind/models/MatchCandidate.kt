package com.tukorea.echomind.models

import java.io.Serializable

/**
 * 매칭 후보 정보를 담는 데이터 모델
 */
data class MatchCandidate(
    val profile: PersonalityProfile,
    val matchScore: Int,
    val similarityScore: Double,
    val chemistryScore: Double,
    val activityScore: Double,
    val relativeTraits: List<RelativeTrait> = emptyList(),
    val myBig5: List<Double> = listOf(50.0, 50.0, 50.0, 50.0, 50.0),
    val candBig5: List<Double> = listOf(50.0, 50.0, 50.0, 50.0, 50.0),
    val myLineCount: Int = 0,
    val candLineCount: Int = 0,
    val mbtiScore: Int = 0,
    val socioScore: Int = 0,
    val mbtiLabel: String = "Neutral",
    val socioQuadraSame: Boolean = false,
    val mbtiWeight: Float = 1.0f,
    val socioWeight: Float = 1.0f
) : Serializable

/**
 * 상대방의 성격 특징 키워드를 담는 클래스
 */
data class RelativeTrait(
    val name: String,
    val label: String,
    val color: String
) : Serializable
