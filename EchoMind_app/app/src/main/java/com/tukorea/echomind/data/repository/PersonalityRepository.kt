package com.tukorea.echomind.data.repository

import com.google.gson.Gson
import com.tukorea.echomind.data.api.ChatMessage
import com.tukorea.echomind.data.api.ChatRequest
import com.tukorea.echomind.data.api.OpenAIService
import com.tukorea.echomind.data.api.ResponseFormat
import com.tukorea.echomind.models.PersonalityProfile
import com.tukorea.echomind.parser.KakaoParser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class PersonalityRepository(
    private val apiService: OpenAIService,
    private val parser: KakaoParser,
    private val apiKey: String
) {
    private val gson = Gson()

    suspend fun analyzeChat(chatLines: List<String>, targetName: String): Result<PersonalityProfile> = withContext(Dispatchers.IO) {
        try {
            // 1. 대화 내역 파싱 및 정제
            val parsedLines = parser.parseTargetLines(chatLines, targetName)
            if (parsedLines.isEmpty()) {
                return@withContext Result.failure(Exception("분석할 대화 내역이 없습니다."))
            }

            // 2. OpenAI 분석용 샘플링 (Python 로직 이식: 최대 120메시지, 18000자)
            val sampleLines = parsedLines.takeLast(120).joinToString("\n")

            // 3. 파이썬 main.py의 정교한 시스템 프롬프트 100% 이식
            val systemPrompt = """
                "당신은 대화 요약/성향 추정 도우미입니다.\n"
                "중요:\n"
                "- 원문 대화 문장을 직접 인용(따옴표 포함)하지 마십시오.\n"
                "- 개인정보/식별정보를 생성하거나 추측하지 마십시오.\n"
                "- 대화방 규범에 따라 달라질 수 있는 말투(존댓말/반말/완곡 표현 등)를 근거로 삼지 마십시오.\n"
                "- 제공된 샘플(정제·마스킹됨)과 수치 신호(평균 길이/질문비율/이모지비율 등)만으로 "
                "MBTI, Big5, 소시오니크를 '추정'하고 이유를 한국어로 제시하십시오.\n"
                "- 한계와 오차 가능성을 caveats에 반드시 포함하십시오.\n\n"
                "Big5 이유 (reasons) 작성:\n"
                "- 각 특성(Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism)마다 "
                "'특성명: 구체적인 이유' 형식의 문장을 작성하십시오.\n"
                "- 예시: 'Openness: 새로운 표현과 실험적인 언어 사용이 빈번함', "
                "'Conscientiousness: 계획적이고 시간 약속을 엄격히 지키는 언어 패턴'\n"
                "- 최소 3~5개의 명확한 이유를 reasons 배열에 포함하십시오.\n\n"
                "출력 형식 요구사항:\n"
                "- 반드시 JSON '객체' 하나만 출력하십시오.\n"
                "- 설명 문장/마크다운/코드블록/여분 텍스트를 절대 포함하지 마십시오.\n"
                "- 키 이름은 아래 계약(json_contract)과 동일해야 합니다.\n"
                "- Big5 점수(scores)와 confidence 값은 영단어(Forty-Five 등)나 문자열이 아닌, 반드시 순수한 숫자(Number) 타입으로 반환하십시오."
            """.trimIndent()

            // 파이썬의 json_contract 구조 정의
            val jsonContract = """
                {
                  "summary": { "one_paragraph": "string", "communication_style_bullets": ["string"] },
                  "mbti": { "type": "INTJ", "confidence": 0.9, "reasons": ["string"] },
                  "big5": {
                    "scores_0_100": { "openness": 80, "conscientiousness": 70, "extraversion": 50, "agreeableness": 60, "neuroticism": 40 },
                    "confidence": 0.8,
                    "reasons": ["string"]
                  },
                  "socionics": { "type": "LII", "confidence": 0.7, "reasons": ["string"] },
                  "caveats": ["string"]
                }
            """.trimIndent()

            val request = ChatRequest(
                model = "gpt-5-mini", // 모델명 반영
                messages = listOf(
                    ChatMessage("system", systemPrompt + "\n\nJSON 구조 계약:\n" + jsonContract),
                    ChatMessage("user", "이 대화 내역을 분석해줘:\n$sampleLines")
                ),
                responseFormat = ResponseFormat("json_object")
            )

            // 4. API 호출
            val response = apiService.getChatCompletion("Bearer $apiKey", request)
            val content = response.choices.firstOrNull()?.message?.content
                ?: return@withContext Result.failure(Exception("API 응답이 비어있습니다."))

            // 5. 고도화된 모델로 파싱
            val profile = gson.fromJson(content, PersonalityProfile::class.java)
                .copy(userId = "current_user", name = targetName, lineCount = parsedLines.size)

            Result.success(profile)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
