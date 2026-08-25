package com.tukorea.echomind.data.api

import retrofit2.Response
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.POST

interface CreditService {
    @GET("api/credits")
    suspend fun getCredits(): Response<CreditResponse>

    @FormUrlEncoded
    @POST("api/credits")
    suspend fun purchaseCredits(@Field("credits") amount: Int): Response<CreditResponse>
}