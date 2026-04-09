import React, { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import {
  appendTranscriptChunk,
  setFinalTranscript,
  finishTranscript,
  completeSegmentTyping,
  setTotalDuration,
  updateSpeakerStats,
  setDetectedLanguage
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
  const teacherSpeakerRef = useRef<string | null>(null);
  const typewriterControllers = useRef<Map<number, AbortController>>(new Map());
  const finishTimeoutRef = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const segmentsRef = useRef<typeof segments>([]);

  const [segmentDisplayTexts, setSegmentDisplayTexts] = useState<string[]>([]);
  const [groupedSegments, setGroupedSegments] = useState<GroupedSegment[]>([]);

  const { segments, currentTypingIndex, teacherSpeaker, detectedLanguage } =
    useAppSelector(s => s.transcript);
  segmentsRef.current = segments;
  teacherSpeakerRef.current = teacherSpeaker;
  const { 
    aiProcessing, 
    uploadedAudioPath, 
    sessionId,
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
        const baseLabel = currentLanguage === "zh" ? "说话人" : labels.student.toUpperCase();
        return `${baseLabel}_${speakerNumber}`;
      }
    
      if (speaker.toLowerCase() === 'speaker') {
        return currentLanguage === "zh" ? "说话人" : labels.student.toUpperCase();
      }
      return speaker;
    }
  }, [detectedLanguage, teacherSpeaker, segments]);

  const finalizeTranscript = () => {
    if (finishedRef.current || !mountedRef.current) return;
    finishedRef.current = true;
    dispatch(finishTranscript());
    
    setTimeout(() => {
      if (mountedRef.current) {
        dispatch(transcriptionComplete());
      }
    }, 150);
    // Guards are reset only when sessionId changes (see useEffect below).
  };

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

        if (mountedRef.current) {
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
    if (
      !aiProcessing || 
      !uploadedAudioPath || 
      streamStartedRef.current ||
      transcriptionDone
    ) {
      console.log('🎯 Transcript stream prevented:', {
        aiProcessing,
        uploadedAudioPath: !!uploadedAudioPath,
        streamStartedRef: streamStartedRef.current,
        transcriptionDone,
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
            
            const chunkData = ev.data;
            if (chunkData.segments && Array.isArray(chunkData.segments)) {
              const processedSegments = chunkData.segments.map((segment: any) => {
                const offset = chunkData.start_time || 0;
                const useOffset = segment.start < offset;

                return {
                  ...segment,
                  start: useOffset ? segment.start + offset : segment.start,
                  end: useOffset ? segment.end + offset : segment.end,
                };
              });
              
              dispatch(appendTranscriptChunk({
                ...chunkData,
                segments: processedSegments
              }));
            } else {
              dispatch(appendTranscriptChunk(chunkData));
            }
          }

          else if (ev.type === "transcript" && typeof ev.token === "string") {
            if (!transcriptionStartedRef.current) {
              transcriptionStartedRef.current = true;
              dispatch(startTranscription());
            }
            dispatch(appendTranscriptChunk({ text: ev.token }));
          }

          else if (ev.type === "final") {
            console.log('📋 Final transcript data received:', ev.data);
            dispatch(setFinalTranscript(ev.data));
            
            if (ev.data.teacher_speaker) {
              console.log('👨‍🏫 Teacher speaker identified:', ev.data.teacher_speaker);
            }
            
            if (ev.data.speaker_text_stats) {
              console.log('📊 Speaker stats received:', ev.data.speaker_text_stats);
              dispatch(updateSpeakerStats(ev.data.speaker_text_stats));
            }
          }

          else if (ev.type === "error") {
            console.error("❌ Transcription error:", ev.message);
            finalizeTranscript();
            break;
          }

          else if (ev.type === "done") {
            console.log("📋 Transcript stream done");

            const latestSegments = segmentsRef.current;
            if (latestSegments.length > 0) {
              const maxEnd = Math.max(...latestSegments.map(s => s.end || 0).filter(end => end > 0));
              if (maxEnd > 0) {
                console.log('⏱️ Setting total duration from segments:', maxEnd);
                dispatch(setTotalDuration(maxEnd));
              }
              
              const speakerStats: { [speaker: string]: number } = {};
              latestSegments.forEach(segment => {
                if (segment.start !== undefined && segment.end !== undefined) {
                  const duration = segment.end - segment.start;
                  speakerStats[segment.speaker] = (speakerStats[segment.speaker] || 0) + duration;
                }
              });
              
              if (Object.keys(speakerStats).length > 0) {
                dispatch(updateSpeakerStats(speakerStats));
              }
            }

            finishTimeoutRef.current = window.setTimeout(() => {
              if (mountedRef.current) {
                finalizeTranscript();
              }
            }, teacherSpeakerRef.current ? 2500 : 3000);

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
    transcriptionDone,
    dispatch
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

  return (
    <div className="transcripts-tab chat-ui-root">
      <div className="transcript-content chat-ui-content">
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