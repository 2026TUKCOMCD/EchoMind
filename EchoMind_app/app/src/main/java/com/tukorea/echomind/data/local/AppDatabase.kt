package com.tukorea.echomind.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

// 상세 필드 추가에 따라 버전을 3으로 올립니다.
@Database(entities = [PersonalityEntity::class], version = 3)
abstract class AppDatabase : RoomDatabase() {
    abstract fun personalityDao(): PersonalityDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "echomind_db"
                )
                // 상세 데이터 구조 변경 시 기존 데이터를 초기화하고 동기화함
                .fallbackToDestructiveMigration()
                .build()
                INSTANCE = instance
                instance
            }
        }
    }
}
