package com.tukorea.echomind.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface PersonalityDao {

    // [저장] 분석 결과를 DB에 저장합니다. (기존 데이터와 충돌 시 덮어씀)
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertResult(result: PersonalityEntity)

    // [역사 조회] 사용자의 모든 분석 기록을 최신순(ID 역순)으로 가져옵니다.
    @Query("SELECT * FROM personality_results WHERE userEmail = :email ORDER BY id DESC")
    suspend fun getAllResultsByUser(email: String): List<PersonalityEntity>

    // [대표 프로필] 특정 사용자의 대표로 설정된 프로필 1개를 가져옵니다.
    @Query("SELECT * FROM personality_results WHERE userEmail = :email AND isRepresentative = 1 LIMIT 1")
    suspend fun getRepresentativeResult(email: String): PersonalityEntity?

    // [대표 해제] 새로운 대표를 설정하기 전, 기존의 모든 대표 설정을 끕니다.
    @Query("UPDATE personality_results SET isRepresentative = 0 WHERE userEmail = :email")
    suspend fun clearRepresentative(email: String)

    // [최신 조회] 대표 프로필이 없을 경우를 대비해 가장 최근 기록 1개를 가져옵니다.
    @Query("SELECT * FROM personality_results WHERE userEmail = :email ORDER BY id DESC LIMIT 1")
    suspend fun getLatestResultByUser(email: String): PersonalityEntity?

    // [삭제] 특정 사용자의 모든 분석 기록을 삭제합니다.
    @Query("DELETE FROM personality_results WHERE userEmail = :email")
    suspend fun clearResultsByUser(email: String)
}