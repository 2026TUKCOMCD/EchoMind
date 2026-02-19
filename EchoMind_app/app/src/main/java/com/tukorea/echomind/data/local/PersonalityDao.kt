package com.tukorea.echomind.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface PersonalityDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertResult(result: PersonalityEntity)

    // [핵심] 특정 사용자의 분석 결과만 가져오도록 수정
    @Query("SELECT * FROM personality_results WHERE userEmail = :email ORDER BY timestamp DESC")
    suspend fun getResultsByUser(email: String): List<PersonalityEntity>

    // 특정 사용자의 최신 결과 1개만 조회
    @Query("SELECT * FROM personality_results WHERE userEmail = :email ORDER BY timestamp DESC LIMIT 1")
    suspend fun getLatestResultByUser(email: String): PersonalityEntity?

    @Query("DELETE FROM personality_results WHERE userEmail = :email")
    suspend fun clearResultsByUser(email: String)
}
