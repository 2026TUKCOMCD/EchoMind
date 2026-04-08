package com.tukorea.echomind

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
 * [EchoMind 단일화 통신 엔진]
 * 모든 기능이 이 객체를 통해 로그인 세션을 공유합니다.
 */
object GlobalClient {
    private const val BASE_URL = "https://echomind.gleeze.com/"

    private val cookieManager = CookieManager().apply {
        setCookiePolicy(CookiePolicy.ACCEPT_ALL)
    }

    val okHttpClient = OkHttpClient.Builder()
        .cookieJar(JavaNetCookieJar(cookieManager))
        .connectTimeout(5, TimeUnit.MINUTES)
        .readTimeout(5, TimeUnit.MINUTES)
        .writeTimeout(5, TimeUnit.MINUTES)
        .retryOnConnectionFailure(true)
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.HEADERS
        })
        .build()

    val retrofit: Retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(ScalarsConverterFactory.create()) 
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    interface ApiService {
        @GET("/")
        suspend fun getHomeHtml(): Response<String>

        @GET("download_json")
        suspend fun getMyProfileJson(): Response<ProfileRootDto>

        // [추가] 분석 기록(역사) 페이지의 HTML을 가져오는 기능 (ID 및 전체 목록 확보용)
        @GET("history")
        suspend fun getHistoryHtml(): Response<String>

        @POST("set_representative/{resultId}")
        suspend fun setRepresentative(@Path("resultId") resultId: Int): Response<ResponseBody>
    }

    val apiService: ApiService by lazy {
        retrofit.create(ApiService::class.java)
    }
}
