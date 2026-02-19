package com.tukorea.echomind.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "personality_results")
data class PersonalityEntity(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val userEmail: String,
    val name: String,
    val mbti: String,
    val mbtiConfidence: Double,
    val mbtiReasons: String, // [추가] MBTI 근거 상세 텍스트
    val openness: Double,
    val conscientiousness: Double,
    val extraversion: Double,
    val agreeableness: Double,
    val neuroticism: Double,
    val big5Reasons: String, // [추가] Big5 근거 상세 텍스트
    val socionics: String,
    val socionicsReasons: String, // [추가] 소시오닉스 근거 상세 텍스트
    val lineCount: Int,
    val summary: String,
    val styleBullets: String, // [추가] 대화 스타일 불렛 포인트
    val caveats: String,      // [추가] 주의사항 텍스트
    val timestamp: Long = System.currentTimeMillis()
)
