package com.tukorea.echomind.data.api

import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.*

interface MatchService {
    
    @GET("/")
    @Headers("Accept: text/html", "Connection: close")
    suspend fun getHomeHtml(): Response<String>

    @GET("result")
    @Headers("Accept: text/html", "Connection: close")
    suspend fun getResultHtml(): Response<String>

    @GET("matching")
    @Headers("Accept: text/html", "Connection: close")
    suspend fun getMatchingHtml(): Response<String>

    @GET("inbox")
    @Headers("Accept: text/html", "Connection: close")
    suspend fun getInboxHtml(): Response<String>

    @GET("admin/api/users")
    @Headers("Accept: application/json")
    suspend fun getMatchingCandidates(): Response<AdminUserListResponse>

    @POST("apply_match/{receiver_id}")
    suspend fun applyMatch(
        @Path("receiver_id") receiverId: Int
    ): Response<ResponseBody>

    @GET("respond_match/{request_id}/{action}")
    suspend fun respondMatch(
        @Path("request_id") requestId: Int,
        @Path("action") action: String
    ): Response<ResponseBody>

    @POST("unmatch/request/{request_id}")
    suspend fun requestUnmatch(
        @Path("request_id") requestId: Int
    ): Response<ResponseBody>

    @GET("unmatch/respond/{request_id}/{action}")
    suspend fun respondUnmatch(
        @Path("request_id") requestId: Int,
        @Path("action") action: String
    ): Response<ResponseBody>

    @POST("cancel_match_request/{request_id}")
    suspend fun cancelMatchRequest(
        @Path("request_id") requestId: Int
    ): Response<ResponseBody>

    // 웹과 동일하게 .txt 파일을 업로드하여 서버가 분석하게 함
    @Multipart
    @POST("upload")
    @Headers("Accept: text/html")
    suspend fun uploadChatFile(
        @Part file: MultipartBody.Part,
        @Part("target_name") targetName: RequestBody
    ): Response<String>

    @Headers("Accept: application/json")
    @GET("download_json")
    suspend fun getMyProfileFromServer(): Response<ProfileRootDto>
}
