package com.tukorea.echomind.data.api

import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.POST

interface BlindMatchService {
    @GET("api/blind-inbox")
    suspend fun getInbox(): Response<BlindInboxResponse>

    @POST("api/blind-match/queue/enter")
    suspend fun enterQueue(): Response<BlindActionResponse>

    @POST("api/blind-match/queue/leave")
    suspend fun leaveQueue(): Response<BlindActionResponse>

    @GET("api/blind-match/queue/status")
    suspend fun getQueueStatus(): Response<BlindQueueStatusResponse>

    @POST("api/blind-match/{matchId}/respond/{action}")
    suspend fun respond(@retrofit2.http.Path("matchId") matchId: Int, @retrofit2.http.Path("action") action: String): Response<BlindActionResponse>

    @GET("api/blind-chat/{matchCode}/messages")
    suspend fun getMessages(@retrofit2.http.Path("matchCode") matchCode: String): Response<BlindChatResponse>

    @POST("api/blind-chat/{matchCode}/send")
    suspend fun sendMessage(@retrofit2.http.Path("matchCode") matchCode: String, @retrofit2.http.Body body: Map<String, String>): Response<BlindActionResponse>

    @POST("api/blind-match/{matchId}/send-profile")
    suspend fun sendProfile(@retrofit2.http.Path("matchId") matchId: Int): Response<BlindActionResponse>

    @POST("api/blind-match/{matchId}/end")
    suspend fun endMatch(@retrofit2.http.Path("matchId") matchId: Int): Response<BlindActionResponse>
}

data class BlindActionResponse(
    val success: Boolean = false,
    val message: String = ""
)

data class BlindQueueStatusResponse(
    val status: String = "IDLE",
    val matchCode: String? = null,
    val elapsedSeconds: Int = 0
)

data class BlindInboxResponse(
    val success: Boolean = false,
    val data: BlindInboxData? = null,
    val message: String? = null
)

data class BlindInboxData(
    val active: List<BlindMatchSummary> = emptyList(),
    val completed: List<BlindMatchSummary> = emptyList()
)

data class BlindMatchSummary(
    val match_id: Int = 0,
    val match_code: String = "",
    val partner_nickname: String = "블라인드 사용자",
    val status: String = "",
    val last_message: String = "",
    val unread_count: Int = 0,
    val updated_at: String? = null
)

data class BlindChatResponse(
    val status: String = "",
    val profile_status: BlindProfileStatus? = null,
    val messages: List<BlindMessageDto> = emptyList(),
    val redirect_url: String? = null
)

data class BlindProfileStatus(
    val i_sent: Boolean = false,
    val partner_sent: Boolean = false
)

data class BlindMessageDto(
    val id: Int = 0,
    val content: String = "",
    val created_at: String = "",
    val is_me: Boolean = false,
    val is_read: Boolean = false
)
