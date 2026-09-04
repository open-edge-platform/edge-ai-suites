import React, { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import {
  completeSegmentTyping,
  setDetectedLanguage
} from "../../redux/slices/transcriptSlice";
import { typewriterStream } from "../../utils/typewriterStream";
import { useFeatureConfig } from "../../hooks/useFeatureConfig";
import "../../assets/css/TranscriptsTab.css";

interface GroupedSegment {
  id: string;
  speaker: string;
  combinedText: string;
  originalSegments: number[];
  isComplete: boolean;
  isCurrentlyTyping: boolean;
}

type SupportedLanguage = "en" | "zh";

const SPEAKER_LABELS: Record<
  SupportedLanguage,
  { teacher: string; student: string }
> = {
  en: {
    teacher: "TEACHER",
    student: "STUDENT",
  },
  zh: {
    teacher: "老师",
    student: "学生",
  },
};

// Renders the transcript the pipeline produces (see redux/useAudioPipeline):
// groups consecutive segments per speaker and types them out. The stream itself
// is not owned here — this tab is unmounted whenever another tab is selected.
const TranscriptsTab: React.FC = () => {
  const dispatch = useAppDispatch();
  const { t } = useTranslation();
  const typewriterControllers = useRef<Map<number, AbortController>>(new Map());
  const mountedRef = useRef(true);

  const { guard, loaded: featuresLoaded } = useFeatureConfig();
  const asrChunkingEnabled = !featuresLoaded || guard.isAsrChunkingEnabled();

  const [segmentDisplayTexts, setSegmentDisplayTexts] = useState<string[]>([]);
  const [groupedSegments, setGroupedSegments] = useState<GroupedSegment[]>([]);

  const { segments, currentTypingIndex, teacherSpeaker, detectedLanguage } =
    useAppSelector(s => s.transcript);
  const {
    aiProcessing,
    uploadedAudioPath,
    transcriptionDone,
  } = useAppSelector(s => s.ui);

  const detectLanguage = (text: string): SupportedLanguage => {
    const chineseRegex = /[\u4e00-\u9fff]/;
    if (chineseRegex.test(text)) return "zh";
    return "en";
  };

  const getSpeakerLabel = useCallback((speaker: string): string => {
    const hasChineseText = segments.some(s => /[\u4e00-\u9fff]/.test(s.text || ""));
    const currentLanguage = detectedLanguage || (hasChineseText ? "zh" : "en");
    const labels = SPEAKER_LABELS[currentLanguage] || SPEAKER_LABELS.en;
    
    if (!teacherSpeaker) {
      if (currentLanguage === "zh") {
        const match = speaker.match(/speaker_(\d+)/i);
        if (match) {
          return `说话人_${match[1]}`;
        }
        if (speaker.toLowerCase() === "speaker") {
          return "说话人";
        }
      }
      return speaker.toUpperCase(); 
    }
    
    if (speaker === teacherSpeaker) {
      return labels.teacher; 
    } else if (speaker === "student") {
      return labels.student;
    } else {
      const speakerMatch = speaker.match(/speaker_(\d+)/i);
      if (speakerMatch) {
        const speakerNumber = speakerMatch[1];
        const baseLabel = currentLanguage === "zh" ? labels.student : labels.student.toUpperCase();
        return `${baseLabel}_${speakerNumber}`;
      }

      if (speaker.toLowerCase() === 'speaker') {
        return currentLanguage === "zh" ? labels.student : labels.student.toUpperCase();
      }
      return speaker;
    }
  }, [detectedLanguage, teacherSpeaker, segments]);

  useEffect(() => {
    if (segments.length > 0) {
      const allText = segments.map(seg => seg.text).join(" ");
      const detected = detectLanguage(allText);
      if (detected !== detectedLanguage) {
        dispatch(setDetectedLanguage(detected));
        console.log(`🌐 Language detected: ${detected}`);
      }
    }
  }, [segments, detectedLanguage, dispatch]);


  useEffect(() => {
    if (segments.length === 0) {
      setGroupedSegments(prev => prev.length === 0 ? prev : []);
      return;
    }

    setGroupedSegments(prevGroups => {
      const newGroups = [...prevGroups];

      for (let i = 0; i < segments.length; i++) {
        const segment = segments[i];
        const speaker = segment.speaker;
        const existingGroupIndex = newGroups.findIndex(group =>
          group.originalSegments.includes(i)
        );
        
        if (existingGroupIndex !== -1) {
          const group = newGroups[existingGroupIndex];
          group.isComplete = group.originalSegments.every(idx => segments[idx].isComplete);
          group.isCurrentlyTyping = group.originalSegments.includes(currentTypingIndex);
          group.combinedText = group.originalSegments.map(idx => segments[idx].text).join(" ");
          continue;
        }

        const lastGroup = newGroups[newGroups.length - 1];
        if (lastGroup && lastGroup.speaker === speaker) {
          lastGroup.originalSegments.push(i);
          lastGroup.combinedText = lastGroup.originalSegments.map(idx => segments[idx].text).join(" ");
          lastGroup.isComplete = lastGroup.originalSegments.every(idx => segments[idx].isComplete);
          lastGroup.isCurrentlyTyping = lastGroup.originalSegments.includes(currentTypingIndex);
        } else {
          const newGroup: GroupedSegment = {
            id: `${speaker}-${i}`,
            speaker: speaker,
            combinedText: segment.text,
            originalSegments: [i],
            isComplete: segment.isComplete || false,
            isCurrentlyTyping: i === currentTypingIndex
          };
          newGroups.push(newGroup);
        }
      }
      
      return newGroups;
    });
  }, [segments, currentTypingIndex]);

  useEffect(() => {
    setSegmentDisplayTexts(prev => {
      const next = [...prev];
      while (next.length < segments.length) next.push("");
      return next;
    });
  }, [segments.length]);


  useEffect(() => {
    if (
      currentTypingIndex < 0 ||
      currentTypingIndex >= segments.length ||
      !mountedRef.current
    ) {
      return;
    }

    const idx = currentTypingIndex;
    const segment = segments[idx];

    const prev = typewriterControllers.current.get(idx);
    if (prev) prev.abort();

    const controller = new AbortController();
    typewriterControllers.current.set(idx, controller);

    const run = async () => {
      try {
        let acc = segmentDisplayTexts[idx] || "";
        if (acc.length > segment.text.length) {
          acc = segment.text.slice(0, acc.length);
        }

        const remaining = segment.text.slice(acc.length);
        if (remaining.length === 0) {
          if (mountedRef.current) {
            dispatch(completeSegmentTyping(idx));
          }
          return;
        }

        for await (const part of typewriterStream(remaining, 150, controller.signal)) {
          if (controller.signal.aborted || !mountedRef.current) return;
          acc += part;
          setSegmentDisplayTexts(prev => {
            const copy = [...prev];
            copy[idx] = acc;
            return copy;
          });
        }

        if (!controller.signal.aborted && mountedRef.current) {
          dispatch(completeSegmentTyping(idx));
        }
      } catch {
        if (!controller.signal.aborted && mountedRef.current) {
          setSegmentDisplayTexts(prev => {
            const copy = [...prev];
            copy[idx] = segment.text;
            return copy;
          });
          dispatch(completeSegmentTyping(idx));
        }
      }
    };

    run();

    // Abort this segment's typewriter when the cursor moves on (or on unmount)
    // so a stale run can't dispatch completeSegmentTyping for an old index.
    return () => {
      controller.abort();
      typewriterControllers.current.delete(idx);
    };
  }, [currentTypingIndex]);

  useEffect(() => {
    segments.forEach((seg, i) => {
      if (seg.isComplete && i !== currentTypingIndex) {
        setSegmentDisplayTexts(prev => {
          const copy = [...prev];
          copy[i] = seg.text;
          return copy;
        });
      }
    });
  }, [segments, currentTypingIndex]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      typewriterControllers.current.forEach(c => c.abort());
      typewriterControllers.current.clear();
    };
  }, []);

  const getDisplayText = useCallback((group: GroupedSegment): string => {
    if (group.isComplete) {
      return group.combinedText;
    }

    if (group.isCurrentlyTyping) {
      const typingSegmentIndex = group.originalSegments.find(i => i === currentTypingIndex);
      if (typingSegmentIndex !== undefined) {
        let displayText = "";
        for (let i = 0; i < group.originalSegments.length; i++) {
          const segmentIndex = group.originalSegments[i];
          if (segmentIndex < currentTypingIndex) {
            displayText += (displayText ? " " : "") + (segments[segmentIndex]?.text ?? "");
          } else if (segmentIndex === currentTypingIndex) {
            const typingText = segmentDisplayTexts[segmentIndex] || "";
            displayText += (displayText ? " " : "") + typingText;
            break;
          }
        }
        return displayText;
      }
    }

    let displayText = "";
    for (const segmentIndex of group.originalSegments) {
      const seg = segments[segmentIndex];
      if (!seg) continue;
      if (segmentIndex <= currentTypingIndex || seg.isComplete) {
        const text = seg.isComplete
          ? seg.text
          : (segmentDisplayTexts[segmentIndex] || "");
        displayText += (displayText ? " " : "") + text;
      }
    }
    return displayText;
  }, [currentTypingIndex, segments, segmentDisplayTexts]);

  const isGroupVisible = useCallback((group: GroupedSegment): boolean => {
    return group.originalSegments.some(i => i <= currentTypingIndex || !!segments[i]?.isComplete);
  }, [currentTypingIndex, segments]);

  const isGroupTyping = useCallback((group: GroupedSegment): boolean => {
    if (!group.isCurrentlyTyping) return false;
    const displayText = getDisplayText(group);
    return displayText.length < group.combinedText.length;
  }, [getDisplayText]);

  const renderedGroups = useMemo(() => {
    return groupedSegments.map((group) => {
      const visible = isGroupVisible(group);
      const displayText = getDisplayText(group);
      const showCursor = isGroupTyping(group);
      
      const speakerLabel = getSpeakerLabel(group.speaker);
      const hasChineseText = segments.some(s => /[\u4e00-\u9fff]/.test(s.text || ""));
      const currentLanguage = detectedLanguage || (hasChineseText ? "zh" : "en");
      const teacherLabel = SPEAKER_LABELS[currentLanguage].teacher;
      const isTeacher = speakerLabel === teacherLabel;

      return {
        ...group,
        visible,
        displayText,
        showCursor,
        speakerLabel,
        isTeacher
      };
    });
  }, [groupedSegments, isGroupVisible, getDisplayText, isGroupTyping, getSpeakerLabel, detectedLanguage]);

  const visibleGroups = useMemo(
    () => renderedGroups.filter(g => g.visible && (g.displayText?.trim().length ?? 0) > 0),
    [renderedGroups]
  );

  // Whole-file mode emits nothing until the entire recording is transcribed
  const showWholeFileNotice =
    !asrChunkingEnabled &&
    aiProcessing &&
    !transcriptionDone &&
    uploadedAudioPath !== "MICROPHONE" &&
    visibleGroups.length === 0;

  return (
    <div className="transcripts-tab chat-ui-root">
      <div className="transcript-content chat-ui-content">
        {showWholeFileNotice && (
          <div className="transcript-placeholder transcript-processing-notice">
            <span className="transcript-processing-spinner" aria-hidden="true" />
            <span>{t('transcript.processingWholeFile')}</span>
          </div>
        )}
        {visibleGroups.length > 0 && (
          <div className="transcript-list chat-ui-list">
            {visibleGroups.map((group) => (
              <div
                key={group.id}
                className={`chat-row ${group.isTeacher ? "teacher-row" : "student-row"}`}
              >
                <div className={`chat-bubble ${group.isTeacher ? "teacher-bubble" : "student-bubble"}`}>
                  <div className="speaker-label">
                    {group.speakerLabel}
                  </div>
                  <div className="speaker-text">
                    {group.displayText}
                    {group.showCursor && (
                      <span className="typewriter-cursor">|</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default TranscriptsTab;