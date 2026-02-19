package com.tukorea.echomind.domain

import com.tukorea.echomind.models.*
import kotlin.math.log2
import kotlin.math.pow
import kotlin.math.sqrt

class MatchEngine {

    /**
     * 내 프로필과 후보자 리스트를 받아 점수를 계산하고 정렬하여 반환
     */
    fun getMatchingResults(
        myProfile: PersonalityProfile,
        candidates: List<PersonalityProfile>
    ): List<MatchCandidate> {
        return candidates.map { candidateProfile ->
            calculateCandidate(myProfile, candidateProfile)
        }.sortedByDescending { it.matchScore }
    }

    private fun calculateCandidate(me: PersonalityProfile, target: PersonalityProfile): MatchCandidate {
        // 안전한 데이터 추출 (Null 방지 및 기본값 50.0 설정)
        val meBig5 = me.big5?.scores_0_100 ?: Big5Scores()
        val targetBig5 = target.big5?.scores_0_100 ?: Big5Scores()

        // 1. 유사성 (Similarity) - 50%
        val simScore = calculateCosineSimilarity(
            doubleArrayOf(
                meBig5.openness, 
                meBig5.conscientiousness, 
                meBig5.extraversion, 
                meBig5.agreeableness, 
                meBig5.neuroticism
            ),
            doubleArrayOf(
                targetBig5.openness, 
                targetBig5.conscientiousness, 
                targetBig5.extraversion, 
                targetBig5.agreeableness, 
                targetBig5.neuroticism
            )
        )
        val similarityScore = (simScore + 1) / 2.0

        // 2. 케미스트리 (Chemistry) - 40%
        val mbtiMatch = RelationshipBrain.analyzeRelationship(
            me.mbti?.type ?: "", 
            target.mbti?.type ?: ""
        )
        val socionicsScore = RelationshipBrain.getSocionicsScore(
            me.socionics?.type ?: "", 
            target.socionics?.type ?: ""
        )
        val chemistryScore = (mbtiMatch.score * 0.7) + (socionicsScore * 0.3)

        // 3. 활동성 (Activity) - 10%
        val activityScore = calculateActivityScore(me.lineCount, target.lineCount)

        // 최종 합산 (0~100점)
        val totalScore = (similarityScore * 0.5 + chemistryScore * 0.4 + activityScore * 0.1) * 100

        // 특징적인 성향 추출 (UI용)
        val relativeTraits = mutableListOf<RelativeTrait>()
        if (targetBig5.extraversion > 70) relativeTraits.add(RelativeTrait("외향성", "높음", "#3B82F6"))
        if (targetBig5.agreeableness > 70) relativeTraits.add(RelativeTrait("우호성", "높음", "#10B981"))

        return MatchCandidate(
            profile = target,
            matchScore = totalScore.toInt(),
            similarityScore = similarityScore,
            chemistryScore = chemistryScore,
            activityScore = activityScore,
            relativeTraits = relativeTraits
        )
    }

    private fun calculateCosineSimilarity(vectorA: DoubleArray, vectorB: DoubleArray): Double {
        var dotProduct = 0.0
        var normA = 0.0
        var normB = 0.0
        for (i in vectorA.indices) {
            dotProduct += vectorA[i] * vectorB[i]
            normA += vectorA[i].pow(2.0)
            normB += vectorB[i].pow(2.0)
        }
        return if (normA == 0.0 || normB == 0.0) 0.0 else dotProduct / (sqrt(normA) * sqrt(normB))
    }

    private fun calculateActivityScore(countA: Int, countB: Int): Double {
        if (countA < 10 || countB < 10) return 0.5
        val ratio = if (countA > countB) countA.toDouble() / countB else countB.toDouble() / countA
        return 1.0 / (log2(ratio) + 1.0)
    }
}
