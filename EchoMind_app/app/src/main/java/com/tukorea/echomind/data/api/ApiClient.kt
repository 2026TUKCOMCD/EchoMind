package com.tukorea.echomind.data.api

import com.google.gson.GsonBuilder
import okhttp3.ConnectionPool
import okhttp3.JavaNetCookieJar
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.converter.scalars.ScalarsConverterFactory
import java.net.CookieManager
import java.util.concurrent.TimeUnit

object ApiClient {
    private const val BASE_URL = "http://10.0.2.2:5000/"

    private val cookieManager = CookieManager()

    private val okHttpClient = OkHttpClient.Builder()
        .cookieJar(JavaNetCookieJar(cookieManager))
        // [핵심] 로컬 서버와의 연결 불안정 해결을 위한 설정
        .protocols(listOf(Protocol.HTTP_1_1)) // HTTP/1.1 강제 (로컬 Flask 서버 최적화)
        .connectionPool(ConnectionPool(0, 1, TimeUnit.NANOSECONDS)) // 연결 풀링 비활성화 (매번 새 연결)
        .retryOnConnectionFailure(true) // 실패 시 자동 재시도
        
        .connectTimeout(60, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.HEADERS // 로깅 레벨 조정
        })
        .build()

    private val gson = GsonBuilder()
        .setLenient()
        .create()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(ScalarsConverterFactory.create())
        .addConverterFactory(GsonConverterFactory.create(gson))
        .build()

    val authService: AuthService = retrofit.create(AuthService::class.java)
    val matchService: MatchService = retrofit.create(MatchService::class.java)
    val chatService: ChatService = retrofit.create(ChatService::class.java)
    val openAIService: OpenAIService = retrofit.create(OpenAIService::class.java)
}
