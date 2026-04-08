package com.tukorea.echomind.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

// [버전 업데이트] 필드 추가(id, isRepresentative 등)를 반영하기 위해 버전을 3으로 설정합니다.
@Database(entities = [PersonalityEntity::class], version = 3, exportSchema = false)
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
                    // [핵심 솔루션] DB 구조가 바뀌었을 때 앱이 종료되지 않도록 기존 데이터를 초기화하고 새로 구성합니다.
                    .fallbackToDestructiveMigration()
                    .build()
                INSTANCE = instance
                instance
            }
        }
    }
}