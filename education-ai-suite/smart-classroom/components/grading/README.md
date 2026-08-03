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