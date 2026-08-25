package com.tukorea.echomind.data.api

import retrofit2.Response
import retrofit2.http.GET

interface ActivityService {
    @GET("api/activity")
    suspend fun getActivity(): Response<ActivityResponse>
}