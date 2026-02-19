package com.tukorea.echomind.data.api

import com.google.gson.annotations.SerializedName

data class MessageListResponse(
    val messages: List<MessageDto>
)

data class MessageDto(
    val id: Int,
    @SerializedName("sender_id") val senderId: Int,
    val content: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("is_me") val isMe: Boolean,
    @SerializedName("is_read") val isRead: Boolean
)

data class SendMessageRequest(
    val content: String
)
