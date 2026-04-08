package com.tukorea.echomind.models

import java.io.Serializable

data class GroupRoom(
    val id: Int,
    val roomCode: String,
    val name: String,
    val description: String,
    val currentParticipants: Int,
    val maxParticipants: Int,
    val isJoined: Boolean,
    val canJoin: Boolean,
    val reason: String?
) : Serializable
