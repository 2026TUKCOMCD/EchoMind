package com.tukorea.echomind.data.api

import retrofit2.Response
import retrofit2.http.*

interface ChatService {
    
    // 채팅방에 진입했을 때만 호출하여 읽음 처리를 유발함
    @GET("api/chat/{request_id}/messages")
    suspend fun getChatMessages(
        @Path("request_id") requestId: Int
    ): Response<MessageListResponse>

    @POST("api/chat/{request_id}/send")
    suspend fun sendMessage(
        @Path("request_id") requestId: Int,
        @Body request: SendMessageRequest
    ): Response<ActionResponse>
    
    // [신규 가설] 읽음 처리를 하지 않고 개수만 가져오는 API가 서버에 있다면 좋겠지만, 
    // 서버 수정이 불가하므로 기존 로직의 호출 타이밍을 조절합니다.
}
