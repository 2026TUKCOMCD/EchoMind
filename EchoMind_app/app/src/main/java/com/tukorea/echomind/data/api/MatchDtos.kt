package com.tukorea.echomind.data.api

import com.google.gson.annotations.SerializedName
import com.tukorea.echomind.models.PersonalityProfile
import java.io.Serializable

// 서버의 download_json 응답을 위한 최상위 DTO
data class ProfileRootDto(
    @SerializedName("llm_profile") val llmProfile: com.tukorea.echomind.models.PersonalityProfile,
    val meta: MetaDto?,
    @SerializedName("parse_quality") val parseQuality: Map<String, Any>?
)

data class MetaDto(
    @SerializedName("speaker_name") val name: String?
)

data class InboxResponse(
    val requests: List<MatchRequestDto>,
    @SerializedName("sent_requests") val sentRequests: List<SentMatchRequestDto>,
    val matches: List<SuccessfulMatchDto>,
    val alerts: List<NotificationDto>
)

data class MatchRequestDto(
    @SerializedName("request_id") val requestId: Int,
    @SerializedName("sender_id") val senderId: Int,
    @SerializedName("sender_name") val senderName: String,
    @SerializedName("sender_nickname") val senderNickname: String?,
    @SerializedName("sender_mbti") val senderMbti: String?,
    @SerializedName("sender_summary") val senderSummary: String?,
    @SerializedName("match_score") val matchScore: Int,
    val status: String,
    @SerializedName("created_at") val createdAt: String
) : Serializable

data class SentMatchRequestDto(
    @SerializedName("request_id") val requestId: Int,
    @SerializedName("receiver_name") val receiverName: String,
    @SerializedName("receiver_nickname") val receiverNickname: String?,
    val status: String,
    @SerializedName("created_at") val createdAt: String
)

data class SuccessfulMatchDto(
    @SerializedName("request_id") val requestId: Int,
    @SerializedName("user_id") val userId: Int,
    @SerializedName("username") val username: String,
    @SerializedName("nickname") val nickname: String?,
    @SerializedName("last_message") val lastMessage: String?,
    @SerializedName("unread_count") val unreadCount: Int,
    val status: String
) : Serializable

data class NotificationDto(
    @SerializedName("notification_id") val notificationId: Int,
    val message: String,
    @SerializedName("is_read") val isRead: Boolean,
    @SerializedName("created_at") val createdAt: String
)

data class ActionResponse(
    val success: Boolean,
    val message: String
)

data class AdminUserListResponse(
    val success: Boolean,
    val users: List<CandidateDto>
)

data class CandidateDto(
    @field:SerializedName("user_id") val userId: Int,
    val username: String,
    val nickname: String?,
    val mbti: String?,
    val socionics: String?,
    @field:SerializedName("summary_text") val summary: String?,
    val big5: Map<String, Double>?,
    @field:SerializedName("line_count") val lineCount: Int?
)
