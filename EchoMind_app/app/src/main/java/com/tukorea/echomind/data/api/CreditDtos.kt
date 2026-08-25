package com.tukorea.echomind.data.api

import com.google.gson.annotations.SerializedName

data class CreditResponse(
    val success: Boolean = false,
    val balance: Int = 0,
    @SerializedName("analysis_cost") val analysisCost: Int = 290,
    val transactions: List<CreditTransactionDto> = emptyList(),
    val message: String? = null
)

data class CreditTransactionDto(
    val amount: Int = 0,
    val description: String = "",
    @SerializedName("created_at") val createdAt: String? = null
)