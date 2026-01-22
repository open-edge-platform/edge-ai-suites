import React, { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import {
  appendTranscriptChunk,
  setFinalTranscript,
  finishTranscript,
  completeSegmentTyping
} from "../../redux/slices/transcriptSlice";
import {
  startTranscription,
  transcriptionComplete,
} from "../../redux/slices/uiSlice";
import { streamTranscript } from "../../services/api";
import { typewriterStream } from "../../utils/typewriterStream";
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

const TranscriptsTab: React.FC = () => {
  const dispatch = useAppDispatch();
  const streamStartedRef = useRef(false);
  const transcriptionStartedRef = useRef(false);
  const finishedRef = useRef(false);
  const typewriterControllers = useRef<Map<number, AbortController>>(new Map());
  const finishTimeoutRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  const [segmentDisplayTexts, setSegmentDisplayTexts] = useState<string[]>([]);
  const [groupedSegments, setGroupedSegments] = useState<GroupedSegment[]>([]);
  const [detectedLanguage, setDetectedLanguage] = useState<SupportedLanguage>("en");

  const { segments, currentTypingIndex, teacherSpeaker} =
    useAppSelector(s => s.transcript);
  const { 
    aiProcessing, 
    uploadedAudioPath, 
    sessionId,
  } = useAppSelector(s => s.ui);

  const detectLanguage = (text: string): SupportedLanguage => {
    const chineseRegex = /[\u4e00-\u9fff]/;
    if (chineseRegex.test(text)) return "zh";
    return "en";
  };

  const getSpeakerLabel = useCallback((speaker: string): string => {
    const labels = SPEAKER_LABELS[detectedLanguage] || SPEAKER_LABELS.en;
    
    if (!teacherSpeaker) {
      return speaker.toUpperCase(); 
    }
    
    if (speaker === teacherSpeaker) {
      return labels.teacher; 
    } else {
      const speakerMatch = speaker.match(/speaker_(\d+)/i);
      if (speakerMatch) {
        const speakerNumber = speakerMatch[1];
        return `${labels.student.toUpperCase()}_${speakerNumber}`;
      }
    
      if (speaker.toLowerCase() === 'speaker') {
        return labels.student.toUpperCase();
      }
      return speaker;
    }
  }, [detectedLanguage, teacherSpeaker]);

  const finalizeTranscript = () => {
    if (finishedRef.current || !mountedRef.current) return;
    finishedRef.current = true;
    dispatch(finishTranscript());
    
    setTimeout(() => {
      if (mountedRef.current) {
        dispatch(transcriptionComplete());
      }
    }, 150);

    setTimeout(() => {
      streamStartedRef.current = false;
      transcriptionStartedRef.current = false;
    }, 500);
  };


  useEffect(() => {
    if (segments.length > 0) {
      const allText = segments.map(seg => seg.text).join(' ');
      const detected = detectLanguage(allText);
      if (detected !== detectedLanguage) {
        setDetectedLanguage(detected);
        console.log(`🌐 Language detected: ${detected}`);
      }
    }
  }, [segments, detectedLanguage]);

  useEffect(() => {
    if (segments.length === 0) {
      setGroupedSegments([]);
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
          // Add to existing group
          lastGroup.originalSegments.push(i);
          lastGroup.combinedText = lastGroup.originalSegments.map(idx => segments[idx].text).join(" ");
          lastGroup.isComplete = lastGroup.originalSegments.every(idx => segments[idx].isComplete);
          lastGroup.isCurrentlyTyping = lastGroup.originalSegments.includes(currentTypingIndex);
        } else {
          const newGroup: GroupedSegment = {
            id: `${speaker}-${Date.now()}-${i}`, 
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

    const segment = segments[currentTypingIndex];

    const prev = typewriterControllers.current.get(currentTypingIndex);
    if (prev) prev.abort();

    const controller = new AbortController();
    typewriterControllers.current.set(currentTypingIndex, controller);

    const run = async () => {
      let acc = "";
      try {
        for await (const part of typewriterStream(
          segment.text,
          150,
          controller.signal
        )) {
          if (controller.signal.aborted || !mountedRef.current) return;
          acc += part;
          setSegmentDisplayTexts(prev => {
            const copy = [...prev];
            copy[currentTypingIndex] = acc;
            return copy;
          });
        }

        if (mountedRef.current) {
          dispatch(completeSegmentTyping(currentTypingIndex));
        }
      } catch {
        if (!controller.signal.aborted && mountedRef.current) {
          setSegmentDisplayTexts(prev => {
            const copy = [...prev];
            copy[currentTypingIndex] = segment.text;
            return copy;
          });
          dispatch(completeSegmentTyping(currentTypingIndex));
        }
      }
    };

    run();
  }, [currentTypingIndex, segments, dispatch]);

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
    if (
      !aiProcessing || 
      !uploadedAudioPath || 
      streamStartedRef.current 
    ) {
      console.log('🎯 Transcript stream prevented:', {
        aiProcessing,
        uploadedAudioPath: !!uploadedAudioPath,
        streamStartedRef: streamStartedRef.current,
      });
      return;
    }

    console.log('🎯 Starting transcript stream for session:', sessionId);
    streamStartedRef.current = true;
    finishedRef.current = false;

    const run = async () => {
      try {
        const stream = streamTranscript(uploadedAudioPath, sessionId!);

        for await (const ev of stream) {
          if (!mountedRef.current) {
            console.log('📋 Component unmounted, stopping transcript stream');
            return;
          }

          if (ev.type === "transcript_chunk") {
            if (!transcriptionStartedRef.current) {
              transcriptionStartedRef.current = true;
              dispatch(startTranscription());
            }
            dispatch(appendTranscriptChunk(ev.data));
          }

          else if (ev.type === "transcript" && typeof ev.token === "string") {
            if (!transcriptionStartedRef.current) {
              transcriptionStartedRef.current = true;
              dispatch(startTranscription());
            }
            dispatch(appendTranscriptChunk({ text: ev.token }));
          }

          else if (ev.type === "final") {
            dispatch(setFinalTranscript(ev.data));
          }

          else if (ev.type === "error") {
            console.error("❌ Transcription error:", ev.message);
            finalizeTranscript();
            break;
          }

          else if (ev.type === "done") {
            console.log("📋 Transcript stream done");

            finishTimeoutRef.current = window.setTimeout(() => {
              if (mountedRef.current) {
                finalizeTranscript();
              }
            }, teacherSpeaker ? 2500 : 3000);

            break;
          }
        }
      } catch (err) {
        console.error("❌ Transcript stream failed:", err);
        if (mountedRef.current) {
          finalizeTranscript();
        }
      }
    };

    run();
  }, [
    aiProcessing, 
    uploadedAudioPath, 
    sessionId, 
    teacherSpeaker, 
    dispatch,
  ]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      typewriterControllers.current.forEach(c => c.abort());
      typewriterControllers.current.clear();
      if (finishTimeoutRef.current) clearTimeout(finishTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    streamStartedRef.current = false;
    transcriptionStartedRef.current = false;
    finishedRef.current = false;
  }, [sessionId]);

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
            displayText += (displayText ? " " : "") + segments[segmentIndex].text;
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
      if (segmentIndex <= currentTypingIndex || segments[segmentIndex].isComplete) {
        const text = segments[segmentIndex].isComplete 
          ? segments[segmentIndex].text 
          : (segmentDisplayTexts[segmentIndex] || "");
        displayText += (displayText ? " " : "") + text;
      }
    }
    return displayText;
  }, [currentTypingIndex, segments, segmentDisplayTexts]);

  const isGroupVisible = useCallback((group: GroupedSegment): boolean => {
    return group.originalSegments.some(i => i <= currentTypingIndex || segments[i].isComplete);
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
      const teacherLabel = SPEAKER_LABELS[detectedLanguage].teacher;
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


  return (
    <div className="transcripts-tab chat-ui-root">
      <div className="transcript-content chat-ui-content">
        {renderedGroups.length > 0 && (
          <div className="transcript-list chat-ui-list">
            {renderedGroups.map((group) => (
              <div
                key={group.id}
                className={`chat-row ${group.isTeacher ? "teacher-row" : "student-row"}`}
              >
                <div className={`chat-bubble ${group.isTeacher ? "teacher-bubble" : "student-bubble"}`}>
                  <div className="speaker-label">
                    {group.speakerLabel}
                  </div>
                  <div className="speaker-text">
                    {group.visible ? group.displayText : ""}
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