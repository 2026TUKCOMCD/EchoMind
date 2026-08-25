package com.tukorea.echomind.data.local

import androidx.room.*

@Dao
interface PersonalityDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertResult(result: PersonalityEntity)

    @Delete
    suspend fun deleteResult(result: PersonalityEntity)

    @Query("SELECT * FROM personality_results WHERE userEmail = :email ORDER BY timestamp DESC")
    suspend fun getAllResultsByUser(email: String): List<PersonalityEntity>

    @Query("SELECT * FROM personality_results WHERE userEmail = :email AND isRepresentative = 1 LIMIT 1")
    suspend fun getRepresentativeResult(email: String): PersonalityEntity?

    @Query("UPDATE personality_results SET isRepresentative = 0 WHERE userEmail = :email")
    suspend fun clearRepresentative(email: String)

    @Query("DELETE FROM personality_results WHERE userEmail = :email")
    suspend fun clearResultsByUser(email: String)
}
