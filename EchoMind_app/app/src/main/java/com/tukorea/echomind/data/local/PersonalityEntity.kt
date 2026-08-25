package com.tukorea.echomind.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey
import java.io.Serializable

@Entity(tableName = "personality_results")
data class PersonalityEntity(
    @PrimaryKey(autoGenerate = true) val id: Int = 0, // 고유 ID로 변경하여 중복 저장 허용
    val serverResultId: Int,
    val userEmail: String,
    val name: String,
    val mbti: String,
    val mbtiConfidence: Double,
    val mbtiReasons: String,
    val openness: Double,
    val conscientiousness: Double,
    val extraversion: Double,
    val agreeableness: Double,
    val neuroticism: Double,
    val big5Reasons: String,
    val socionics: String,
    val socionicsReasons: String,
    val lineCount: Int,
    val summary: String,
    val styleBullets: String,
    val caveats: String,
    val timestamp: Long = System.currentTimeMillis(),
    var isRepresentative: Boolean = false // 대표 프로필 설정 필드 추가
) : Serializable