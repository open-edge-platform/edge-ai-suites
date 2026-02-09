import React, { useMemo } from "react";
import { useAppSelector } from "../../redux/hooks";
import "../../assets/css/Timeline.css";

interface TimelineSegment {
  speaker: string;
  start: number;
  end: number;
  text: string;
}

type SupportedLanguage = "en" | "zh";

const SPEAKER_LABELS: Record<
  SupportedLanguage,
  { teacher: string; student: string }
> = {
  en: { teacher: "TEACHER", student: "STUDENT" },
  zh: { teacher: "老师", student: "学生" },
};

const Timeline: React.FC = () => {
  const { segments, teacherSpeaker, totalDuration, detectedLanguage } =
    useAppSelector(s => s.transcript);

  const lang = detectedLanguage || "en";
  const labels = SPEAKER_LABELS[lang] ?? SPEAKER_LABELS.en;

  const timelineSegments = useMemo<TimelineSegment[]>(() => {
    return segments
      .filter(s => {
        const t = s.text?.trim() || "";
        return t.length > 2 && !/^[\s\.,!?]*$/.test(t);
      })
      .map(s => ({
        speaker: s.speaker,
        start: s.start ?? 0,
        end: s.end ?? 0,
        text: s.text,
      }));
  }, [segments]);

  const isValidSpeaker = (speaker: string) =>
    /^SPEAKER_\d+$/i.test(speaker);

  const cleanedSegments = useMemo(
    () => timelineSegments.filter(s => isValidSpeaker(s.speaker)),
    [timelineSegments, teacherSpeaker]
  );

  const mergedSegments = useMemo(() => {
    const out: TimelineSegment[] = [];
    for (const seg of cleanedSegments) {
      const last = out[out.length - 1];
      if (
        last &&
        last.speaker === seg.speaker &&
        seg.start - last.end <= 0.8
      ) {
        last.end = seg.end;
        last.text += " " + seg.text;
      } else {
        out.push({ ...seg });
      }
    }
    return out;
  }, [cleanedSegments]);

  const maxDuration = useMemo(() => {
    if (totalDuration && totalDuration > 0) return totalDuration;
    return mergedSegments.length
      ? Math.max(...mergedSegments.map(s => s.end))
      : 0;
  }, [mergedSegments, totalDuration]);

  const speakerDurations = useMemo(() => {
    const map = new Map<string, number>();
    mergedSegments.forEach(s => {
      map.set(s.speaker, (map.get(s.speaker) || 0) + (s.end - s.start));
    });
    return map;
  }, [mergedSegments]);

  const activeSpeakers = useMemo(() => {
    return [...speakerDurations.entries()]
      .filter(([, dur]) => dur >= 1)
      .map(([speaker]) => speaker);
  }, [speakerDurations]);

  const getSpeakerLabel = (speaker: string): string => {
    if (speaker === teacherSpeaker) return labels.teacher;
    if (teacherSpeaker) {
      const match = speaker.match(/SPEAKER_(\d+)/i);
      if (match) {
        const speakerNumber = match[1];
        return `${labels.student}_${speakerNumber}`;
      }
    }
    return speaker;
  };

  const getSpeakerColor = (speaker: string): string => {
    if (speaker === teacherSpeaker) return "#54a00d";

    if (teacherSpeaker && speaker !== teacherSpeaker) {
      const studentColors = ["#2196F3", "#df2ad0", "#1f2ce0", "#f5972b", "#1be025"];
      const match = speaker.match(/SPEAKER_(\d+)/i);
      if (match) {
        const speakerNumber = parseInt(match[1], 10);
        return studentColors[speakerNumber % studentColors.length];
      }
    }
    
    const colors = ["#2196F3", "#FF9800", "#9C27B0", "#f5972b", "#00BCD4"];
    const m = speaker.match(/SPEAKER_(\d+)/i);
    return m ? colors[parseInt(m[1], 10) % colors.length] : "#757575";
  };

  const formatTime = (s: number) =>
    `${Math.floor(s / 60)}:${Math.floor(s % 60)
      .toString()
      .padStart(2, "0")}`;

  console.log('Timeline Debug:', {
    totalSegments: segments.length,
    timelineSegments: timelineSegments.length,
    cleanedSegments: cleanedSegments.length,
    mergedSegments: mergedSegments.length,
    activeSpeakers: activeSpeakers,
    teacherSpeaker: teacherSpeaker,
    maxDuration: maxDuration,
    detectedLanguage: detectedLanguage,
    speakerDurations: Object.fromEntries(speakerDurations),
    sampleSpeakers: segments.slice(0, 5).map(s => s.speaker),

    speakerLabels: activeSpeakers.map(speaker => ({
      original: speaker,
      label: getSpeakerLabel(speaker)
    }))
  });

  if (!activeSpeakers.length || maxDuration <= 0) return null;

  return (
    <div className="timeline-container">
      <div className="timeline-header">
        <h3>{lang === "zh" ? "发言时间轴" : "Speaking Timeline"}</h3>
        <div>
          {lang === "zh" ? "总时长" : "Total Duration"}: {formatTime(maxDuration)}
        </div>
      </div>

      <div className="timeline-content">
        {activeSpeakers.map(speaker => {
          const speakerSegments = mergedSegments.filter(
            s => s.speaker === speaker
          );
          const color = getSpeakerColor(speaker);
          const label = getSpeakerLabel(speaker);

          return (
            <div key={speaker} className="timeline-row">
              <div className="timeline-speaker-info">
                <div className="speaker-label" style={{ color }}>
                  <strong>{label}</strong>
                </div>
              </div>

              <div className="timeline-track">
                <div className="timeline-background" />
                {speakerSegments.map((seg, i) => {
                  const left = (seg.start / maxDuration) * 100;
                  const width = ((seg.end - seg.start) / maxDuration) * 100;
                  if (width <= 0) return null;

                  return (
                    <div
                      key={i}
                      className="timeline-segment"
                      style={{
                        left: `${left}%`,
                        width: `${width}%`,
                        backgroundColor: color,
                      }}
                      title={`${label}: ${formatTime(seg.start)} - ${formatTime(seg.end)}\n${seg.text.substring(0, 100)}...`}
                    />
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Timeline;