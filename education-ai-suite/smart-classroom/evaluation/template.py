templ_sum_en = """\

{transcript}

"""


templ_sum_zh = """\

{transcript}


"""

sys_prompt_score_en = """\
You job is to evaluate a summary about a lecture.
The original lecture audio transcript is provided. 
Based on the transcript, you need to provide two scores. The first is the COMPLETENESS score, which should range from 1 to 100. The second is the RELIABILITY score, which should also range from 1 to 100. 
Below are the criteria for each scoring category:

##COMPLETENESS Scoring Criteria:
The completeness score focuses on whether the summary covers all key points and main information from the audio.
Score 0 to 20: The summary hardly covers any of the main content or key points of the audio .
Score 20 to 40: The summary covers some of the main content and key points but misses many.
Score 40 to 60: The summary covers most of the main content and key points.
Score 60 to 80: The summary is very comprehensive, covering most to nearly all of the main content and key points.
Score 80 to 100: The summary completely covers all the main content and key points of the audio .
##RELIABILITY Scoring Criteria:
The reliability score evaluates the correctness and clarity of the audio summary. It checks for factual errors, misleading statements, and contradictions with the audio content. If the respondent's answer includes details that are not present in the standard answer, as long as these details do not conflict with the correct answer and are reasonable, points should not be deducted.
Score 0 to 20: Contains multiple factual errors and contradictions; presentation is confusing.
Score 20 to 40: Includes several errors and some contradictions; needs clearer presentation.
Score 40 to 60: Generally accurate with minor errors; minimal contradictions; reasonably clear presentation.
Score 60 to 80: Very accurate with negligible inaccuracies; no contradictions; clear and fluent presentation.
Score 80 to 100: Completely accurate with no errors or contradictions; presentation is clear and easy to understand.

----
##INSTRUCTION:
1. Evaluate COMPLETENESS: First, analyze the summary according to the scoring criteria, then provide an integer score between 1 and 100 based on sufficient evidence.
2. Evaluate RELIABILITY: First, analyze the summary according to the scoring criteria, then provide an integer score between 1 and 100 based on sufficient evidence.
3. Output Scores in JSON Format: Present the scores in JSON format as follows:
{'score_completeness': score_comp, 'score_reliability': score_reli, 'total_score': (score_comp + score_reli)/2}
"""

templ_score_en = """\
Score the summary according to the steps in the Instructions. You must end with a JSON dict to store the scores.

Original lecture audio transcript:
"{transcript}"



Summary:
"{summary}"


"""


sys_prompt_score_zh = """\
你的任务是评估一份课堂教学内容总结的质量。
原始课堂的音频文本已提供。
基于该文本，你需要给出两个评分：首先是完整性评分（COMPLETENESS），范围1-100分；其次是可靠性评分（RELIABILITY），范围1-100分。
具体评分标准如下：

##完整性评分标准：
重点评估摘要是否涵盖音频中的所有关键信息和核心内容
0-20分：摘要几乎未涉及音频主要内容与关键点
20-40分：涵盖部分主要内容但遗漏较多关键信息
40-60分：覆盖大部分主要内容与关键点
60-80分：内容非常全面，涵盖绝大部分核心内容与关键点
80-100分：完整覆盖音频所有核心内容与关键信息

##可靠性评分标准：
评估摘要的准确性与表述清晰度，检查是否存在事实错误、误导性陈述或与音频内容矛盾之处。若回答包含标准答案之外但合理且不冲突的细节内容，不应扣分
0-20分：存在多处事实错误和矛盾；表述混乱
20-40分：存在若干错误和部分矛盾；表述清晰度不足
40-60分：基本准确仅有微小错误；极少矛盾；表述较为清晰
60-80分：高度准确几乎无错误；无矛盾；表述清晰流畅
80-100分：完全准确无任何错误矛盾；表述清晰易懂

##操作指令：

完整性评估：先根据评分标准分析总结，基于充分证据给出1-100的整数评分
可靠性评估：先根据评分标准分析总结，基于充分证据给出1-100的整数评分
以JSON格式输出结果：
{'score_completeness': 完整性分数, 'score_reliability': 可靠性分数, 'total_score': (完整性分数+可靠性分数)/2}
"""


templ_score_zh = """\
根据操作指令给以下课堂总结评分，最后将分数输出为一个JSON格式的字典。


原始课堂音频转录文本:
"{transcript}"



课堂总结:
"{summary}"


"""