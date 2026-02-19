package com.tukorea.echomind.data.api

import com.google.gson.annotations.SerializedName

/**
 * OpenAI API 요청/응답을 위한 DTO 클래스들
 */
data class ChatRequest(
    val model: String,
    val messages: List<ChatMessage>,
    @SerializedName("response_format") val responseFormat: ResponseFormat? = null
)

data class ChatMessage(
    val role: String,
    val content: String
)

data class ResponseFormat(
    val type: String
)

data class ChatResponse(
    val choices: List<Choice>
)

data class Choice(
    val message: ChatMessage
)
