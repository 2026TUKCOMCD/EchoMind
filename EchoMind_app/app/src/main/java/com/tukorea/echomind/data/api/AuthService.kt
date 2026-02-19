package com.tukorea.echomind.data.api

import retrofit2.Response
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.POST

/**
 * 파이썬 Flask 서버의 인증 API와 통신하는 인터페이스
 */
interface AuthService {
    @FormUrlEncoded
    @POST("register")
    suspend fun register(
        @Field("email") email: String,
        @Field("password") password: String,
        @Field("username") username: String,
        @Field("nickname") nickname: String?,
        @Field("gender") gender: String?,
        @Field("birth_date") birthDate: String?
    ): Response<Unit>

    @FormUrlEncoded
    @POST("login")
    suspend fun login(
        @Field("email") email: String,
        @Field("password") password: String
    ): Response<Unit>
}
