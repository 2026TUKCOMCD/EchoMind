package com.tukorea.echomind.data.api

import com.google.gson.annotations.SerializedName

data class ActivityResponse(
    val success: Boolean = false,
    val summary: ActivitySummaryDto? = null,
    val activities: List<ActivityDto> = emptyList()
)

data class ActivitySummaryDto(
    @SerializedName("total_count") val totalCount: Int,
    @SerializedName("login_count") val loginCount: Int,
    @SerializedName("analysis_count") val analysisCount: Int,
    @SerializedName("matching_count") val matchingCount: Int,
    @SerializedName("active_days") val activeDays: Int,
    @SerializedName("average_per_day") val averagePerDay: Double,
    @SerializedName("latest_label") val latestLabel: String?,
    @SerializedName("peak_day") val peakDay: PeakDayDto?
)

data class PeakDayDto(
    val date: String,
    val label: String,
    val count: Int
)

data class ActivityDto(
    val type: String = "",
    val message: String = "",
    val detail: String? = null,
    @SerializedName("created_at") val createdAt: String? = null
)
