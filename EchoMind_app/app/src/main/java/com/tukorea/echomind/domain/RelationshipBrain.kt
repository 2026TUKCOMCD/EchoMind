package com.tukorea.echomind.domain

/**
 * MBTI 및 소시오닉스 기반 관계 분석 엔진
 * 파이썬 matcher.py의 RelationshipBrain 로직을 이식함.
 */
object RelationshipBrain {

    // 소시오닉스 쿼드라 그룹 (가치관 공유)
    private val QUADRAS = mapOf(
        "Alpha" to listOf("ILE", "SEI", "ESE", "LII"),
        "Beta" to listOf("EIE", "LSI", "SLE", "IEI"),
        "Gamma" to listOf("SEE", "ILI", "LIE", "ESI"),
        "Delta" to listOf("LSE", "EII", "IEE", "SLI")
    )

    /**
     * MBTI 기반 관계 분석 및 점수 산출
     */
    fun analyzeRelationship(mbtiA: String, mbtiB: String): MatchResult {
        val a = mbtiA.uppercase()
        val b = mbtiB.uppercase()

        if (a.length != 4 || b.length != 4) return MatchResult(0.5, "Unknown")

        val diffs = (0..3).count { a[it] != b[it] }
        val sameEI = a[0] == b[0]
        val sameNS = a[1] == b[1]
        val sameTF = a[2] == b[2]
        val sameJP = a[3] == b[3]

        return when {
            diffs == 4 -> MatchResult(1.0, "Dual (이원 관계)")
            sameEI && !sameNS && !sameTF && !sameJP -> MatchResult(0.9, "Activity (활동 관계)")
            !sameEI && sameNS && sameTF && sameJP -> MatchResult(0.8, "Mirror (거울 관계)")
            diffs == 0 -> MatchResult(0.6, "Identical (동일 관계)")
            // 갈등 관계 예시 (파이썬 로직 참고)
            !sameEI && !sameNS && !sameTF && sameJP -> MatchResult(0.1, "Conflict (갈등 관계)")
            else -> MatchResult(0.5, "Neutral (중립)")
        }
    }

    /**
     * 소시오닉스 기반 쿼드라 점수 (가치관 일치 여부)
     */
    fun getSocionicsScore(typeA: String, typeB: String): Double {
        val quadraA = QUADRAS.entries.find { it.value.contains(typeA.uppercase()) }?.key
        val quadraB = QUADRAS.entries.find { it.value.contains(typeB.uppercase()) }?.key

        return if (quadraA != null && quadraA == quadraB) 1.0 else 0.4
    }

    data class MatchResult(val score: Double, val label: String)
}
