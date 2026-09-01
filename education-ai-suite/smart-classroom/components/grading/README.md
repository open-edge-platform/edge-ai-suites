# Grading Component

## Notes

1. This grading workflow currently supports exam layouts commonly used in mainland China only.
2. Grading quality depends heavily on the model capability.
3. The same model may produce different grading results for the same question across runs.
4. Different models may produce noticeably different final scores.
5. Text recognition is not 100% accurate.
6. In tested Qwen3.5 9B scenarios, INT4 quantization performs noticeably worse than INT8, while INT8 takes longer to run.
7. The grading workflow assumes student papers are organized by directory, with each student separated by folder.

## Usage Guide

1. Prepare a rubric file for the target exam and place it under [rubrics].
2. The grading panel on the right side provides adjustable parameters.
3. Before starting grading, confirm whether the exam page layout is single-column or two-column.
4. For the rest of the configuration options, see [doc/config-reference.md].

## Quick Test

### 1. Prepare test files
1. Copy rubric files from `./samples/rubrics` to `components/grading/rubrics`.
2. The sample set contains some exams:
	- `zh_sample_physics_exam.txt` (Physics, single-column paper)
	- `zh_sample_5th_grade_chinese.txt` (Chinese, single-column paper)
	- `zh_sample_english_exam.txt` (English, two-column paper)
	- `zh_sample_8th_grade_math.txt` (Math, two-column paper)


### 2. Start services and verify health
1. Start Smart Classroom (make sure the Grading feature is enabled).
2. Open the Grading UI home page.
3. Check that all three status indicators are green: `grading / vlm / layout`.
	- If all are green, all required backend services are ready.

### 3. Physics sample (single-column)
1. In the `Rubric` dropdown, select `zh_sample_physics_exam.txt`.
2. Set `paper_path` to the **absolute path** of the physics sample directory:
	- `components/grading/samples/exam/zh_9th_grade_physics_single_column`
3. In the right-side config panel, confirm `page_columns = 1`.
4. Click `Start` to begin grading.

### 4. English sample (two-column)
1. In the `Rubric` dropdown, select `zh_sample_english_exam.txt`.
2. Set `paper_path` to the **absolute path** of the English sample directory:
	- `components/grading/samples/exam/zh_9th_grade_english_double_column`
3. Before clicking `Start`, set `page_columns = 2` in the right-side config panel.
4. Click `Start` to begin grading.

### 5. Check outputs
1. Wait until task status changes from `PENDING/RUNNING` to `COMPLETED`.
2. Results are written to `components/grading/outputs/<task_id>/`, including:
	- `summary.json`
	- `<student_id>/grading_result.json`