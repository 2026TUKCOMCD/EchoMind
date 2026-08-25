package com.tukorea.echomind

import com.google.gson.GsonBuilder
import com.tukorea.echomind.data.api.*
import com.tukorea.echomind.models.ProfileRootDto
import okhttp3.JavaNetCookieJar
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.scalars.ScalarsConverterFactory
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import java.net.CookieManager
import java.net.CookiePolicy
import okhttp3.ResponseBody
import java.util.concurrent.TimeUnit

/**
 * [EchoMind 통합 통신 엔진]
 * 모든 기능이 이 객체를 통해 로그인 세션을 공유하며,
 * 웹 서비스와의 완벽한 연동 및 통신 안정성을 보장합니다.
 */
object GlobalClient {
    private const val BASE_URL = "https://echomind.gleeze.com/"

    // [중요] 단일 쿠키 매니저를 사용하여 로그인 세션을 전역 공유함
    private val cookieManager = CookieManager().apply {
        setCookiePolicy(CookiePolicy.ACCEPT_ALL)
    }

    val okHttpClient = OkHttpClient.Builder()
        .cookieJar(JavaNetCookieJar(cookieManager))
        .connectTimeout(60, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.HEADERS
        })
        .build()

    private val gson = GsonBuilder()
        .setLenient()
        .create()

    val retrofit: Retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(ScalarsConverterFactory.create()) 
        .addConverterFactory(GsonConverterFactory.create(gson))
        .build()

    interface ApiService {
        @GET("/")
        suspend fun getHomeHtml(): Response<String>

        @GET("download_json")
        suspend fun getMyProfileJson(): Response<ProfileRootDto>

        @GET("download_json/{resultId}")
        suspend fun getProfileJson(@Path("resultId") resultId: Int): Response<ProfileRootDto>

        @GET("history")
        suspend fun getHistoryHtml(): Response<String>

        @GET("activity")
        suspend fun getActivityHtml(): Response<String>

        @POST("set_representative/{resultId}")
        suspend fun setRepresentative(@Path("resultId") resultId: Int): Response<ResponseBody>
    }

    val apiService: ApiService by lazy { retrofit.create(ApiService::class.java) }
    
    // 모든 서비스 도메인 통합
    val authService: AuthService by lazy { retrofit.create(AuthService::class.java) }
    val matchService: MatchService by lazy { retrofit.create(MatchService::class.java) }
    val chatService: ChatService by lazy { retrofit.create(ChatService::class.java) }
    val creditService: CreditService by lazy { retrofit.create(CreditService::class.java) }
    val activityService: ActivityService by lazy { retrofit.create(ActivityService::class.java) }
    val blindMatchService: BlindMatchService by lazy { retrofit.create(BlindMatchService::class.java) }
}
