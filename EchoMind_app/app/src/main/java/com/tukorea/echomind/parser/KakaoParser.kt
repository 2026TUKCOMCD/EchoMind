package com.tukorea.echomind.parser

import java.util.regex.Pattern

/**
 * KakaoTalk 대화 내역 파서
 * 파이썬 main.py의 파싱 로직을 Kotlin으로 이식함.
 */
class KakaoParser {
    // 파이썬의 LINE_PATTERNS 대응 정규식
    private val patterns = listOf(
        Pattern.compile("^\\[(.+?)\\]\\s+\\[(.+?)\\]\\s+(.+)$"), // Windows/Android 형식
        Pattern.compile("^(\\d{4}\\.\\s*\\d{1,2}\\.\\s*\\d{1,2}\\.\\s*.+?),\\s*([^:]+?)\\s*:\\s*(.+)$") // iOS 형식
    )

    // 제외할 시스템 메시지 키워드
    private val systemSkipSubstr = listOf(
        "사진", "이모티콘", "동영상", "삭제된 메시지입니다", "파일", "보이스톡", "통화",
        "송금", "입금", "출금"
    )

    /**
     * 특정 대상(targetName)의 대화 내용만 추출
     */
    fun parseTargetLines(lines: List<String>, targetName: String): List<String> {
        val result = mutableListOf<String>()

        for (line in lines) {
            if (line.isBlank()) continue

            var speaker: String? = null
            var message: String? = null

            for (pattern in patterns) {
                val matcher = pattern.matcher(line)
                if (matcher.find()) {
                    if (matcher.groupCount() == 3) {
                        // 패턴 1: [이름] [시간] 메시지
                        if (line.startsWith("[")) {
                            speaker = matcher.group(1).trim()
                            message = matcher.group(3).trim()
                        } 
                        // 패턴 2: 날짜시간, 이름 : 메시지
                        else {
                            speaker = matcher.group(2).trim()
                            message = matcher.group(3).trim()
                        }
                    }
                    break
                }
            }

            if (speaker == targetName && message != null) {
                if (!looksLikeSystemMessage(message)) {
                    val cleaned = cleanText(message)
                    if (cleaned.isNotBlank()) {
                        result.add(cleaned)
                    }
                }
            }
        }
        return result
    }

    private fun looksLikeSystemMessage(text: String): Boolean {
        return systemSkipSubstr.any { text.contains(it) }
    }

    private fun cleanText(text: String): String {
        // URL 제거, 불필요한 공백 제거 등 (Python의 clean_text_ko 로직)
        return text.replace(Regex("https?://\\S+"), " ")
            .replace(Regex("[ㅋㅎ]{2,}"), " ")
            .replace(Regex("[ㅠㅜ]{2,}"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
    }
}
