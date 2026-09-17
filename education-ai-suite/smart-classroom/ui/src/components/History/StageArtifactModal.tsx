// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import React, { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { useTranslation } from 'react-i18next';
import jsMind from 'jsmind';
import 'jsmind/style/jsmind.css';
import '../../assets/css/StageArtifactModal.css';
import Modal from '../Modals/Modal';
import { getSessionArtifactText, type SessionArtifact } from '../../services/api';
import { cleanJsMindContent } from '../../utils/jsmindData';
import { formatSecondsToTime } from '../../utils/timeUtils';
import { reportUrlTransform } from '../../utils/reportMarkdown';

/** One speaker's turn, after the consecutive lines of it have been joined. */
interface ChatTurn {
  id: string;
  speaker: string;
  text: string;
  isTeacher: boolean;
}

// The transcript is written one segment per line as "<speaker>: <text>"
// (components/asr_component.py). A label is short and carries no punctuation,
// which is what keeps this from swallowing a colon inside a sentence.
const SPEAKER_LINE = /^([^:：\s][^:：]{0,23})[:：]\s*(.*)$/;

// Written in whatever language the session ran in, so match both.
const TEACHER_LABEL = /^(teacher|教师|老师)/i;

/** CJK text is not space-separated; joining its segments with one looks wrong. */
const CJK_EDGE = new RegExp('[\\u3000-\\u303f\\u3400-\\u4dbf\\u4e00-\\u9fff\\uff00-\\uffef]$');

function joinSegments(acc: string, next: string): string {
  if (!acc) return next;
  if (!next) return acc;
  return CJK_EDGE.test(acc) ? acc + next : `${acc} ${next}`;
}

/**
 * Turn the stored transcript back into the chat view the live tab shows.
 *
 * The file has one line per ASR segment, so a single sentence arrives as four
 * lines with the same speaker. Concatenating consecutive same-speaker lines into
 * one bubble is what makes it read as a lesson rather than as a log.
 */
function parseTranscript(raw: string): ChatTurn[] {
  const turns: ChatTurn[] = [];

  for (const line of raw.split(/\r?\n/)) {
    const text = line.trim();
    if (!text) continue;

    const match = SPEAKER_LINE.exec(text);
    const last = turns[turns.length - 1];

    // A line with no label continues the turn above it — the ASR only labels a
    // segment when it knows the speaker.
    if (!match) {
      if (last) last.text = joinSegments(last.text, text);
      else turns.push({ id: 't0', speaker: '', text, isTeacher: true });
      continue;
    }

    const [, speaker, body] = match;
    if (last && last.speaker === speaker) {
      last.text = joinSegments(last.text, body.trim());
      continue;
    }
    turns.push({
      id: `${speaker}-${turns.length}`,
      speaker,
      text: body.trim(),
      isTeacher: TEACHER_LABEL.test(speaker),
    });
  }

  return turns.filter((turn) => turn.text.length > 0);
}

/** One entry of result/topics.json. */
interface Topic {
  topic: string;
  start_time: number;
  end_time: number;
}

/**
 * The topic timeline, as the segmentation stage wrote it.
 *
 * Adjacent entries identical in topic *and* in both timestamps are the same
 * finding recorded more than once, which a table would show as three rows the
 * teacher cannot tell apart; a genuine repeat of a topic later in the lesson has
 * different times and survives.
 */
function parseTopics(raw: string): Topic[] {
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed)) throw new Error('topics.json is not a list');

  const topics: Topic[] = [];
  for (const entry of parsed) {
    if (!entry || typeof entry.topic !== 'string') continue;
    const topic: Topic = {
      topic: entry.topic.trim(),
      start_time: Number(entry.start_time),
      end_time: Number(entry.end_time),
    };
    const last = topics[topics.length - 1];
    if (
      last &&
      last.topic === topic.topic &&
      last.start_time === topic.start_time &&
      last.end_time === topic.end_time
    ) {
      continue;
    }
    topics.push(topic);
  }
  return topics;
}

/** The engagement counts of raw/va/class_statistics.json. */
interface ClassStats {
  student_count?: number;
  stand_count?: number;
  raise_up_count?: number;
  duration_sec?: number;
  stand_reid?: { student_id: number; count: number }[];
  raise_reid?: { student_id: number; count: number }[];
}

/**
 * Video analytics, laid out like the live engagement accordion.
 *
 * Reuses that panel's wording (`classStatistics.*`) rather than inventing a
 * second vocabulary for the same three numbers, and shows the per-student
 * tallies underneath, which is what gives the counts meaning: `stand_count: 12`
 * cannot say whether one student stood twelve times or twelve students once.
 */
const StatsPreview: React.FC<{ stats: ClassStats }> = ({ stats }) => {
  const { t } = useTranslation();

  const tiles = [
    { key: 'students', value: stats.student_count, label: t('classStatistics.students') },
    { key: 'stands', value: stats.stand_count, label: t('classStatistics.stands') },
    { key: 'hands', value: stats.raise_up_count, label: t('classStatistics.hands') },
    {
      key: 'duration',
      value: stats.duration_sec,
      label: t('history.duration', 'Duration'),
      text: formatSecondsToTime(stats.duration_sec),
    },
  ].filter((tile) => tile.value != null);

  const boards = [
    { key: 'stand', rows: stats.stand_reid ?? [], label: t('classStatistics.mostActive') },
    {
      key: 'raise',
      rows: stats.raise_reid ?? [],
      label: t('history.mostHands', 'Most hands raised'),
    },
  ].filter((board) => board.rows.length > 0);

  return (
    <div className="artifact-modal-stats">
      <div className="artifact-stat-tiles">
        {tiles.map((tile) => (
          <div key={tile.key} className="artifact-stat-tile">
            <span className="artifact-stat-value">{tile.text ?? tile.value}</span>
            <span className="artifact-stat-label">{tile.label}</span>
          </div>
        ))}
      </div>

      {boards.map((board) => {
        // Bar length is relative to the most active student, as on the live panel.
        const ranked = [...board.rows].sort((a, b) => b.count - a.count);
        const top = ranked[0]?.count ?? 0;
        return (
          <div key={board.key} className="artifact-stat-board">
            <h4 className="artifact-stat-board-title">{board.label}</h4>
            {ranked.map((entry) => (
              <div key={entry.student_id} className="artifact-stat-row">
                <span className="artifact-stat-id">
                  {`${t('classStatistics.studentId')}: ${entry.student_id}`}
                </span>
                <span className="artifact-stat-track">
                  <span
                    className="artifact-stat-bar"
                    style={{ width: `${top > 0 ? (entry.count / top) * 100 : 0}%` }}
                  />
                </span>
                <span className="artifact-stat-count">{entry.count}</span>
              </div>
            ))}
          </div>
        );
      })}

      {tiles.length === 0 && boards.length === 0 && (
        <div className="artifact-modal-note">{t('classStatistics.noData')}</div>
      )}
    </div>
  );
};

/**
 * The mind map, drawn from the node tree the stage wrote.
 *
 * Its own component because jsMind needs a container that is already in the
 * DOM and sized, and needs tearing down again when the pop-up closes. Read-only
 * (`editable: false`): this is a record of a past class, and an edit here would
 * go nowhere.
 */
const MindMapPreview: React.FC<{ source: string }> = ({ source }) => {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    try {
      const jm = new jsMind({
        container,
        theme: 'primary',
        editable: false,
        mode: 'full',
        view: {
          engine: 'svg',
          hmargin: 60,
          vmargin: 40,
          line_width: 2,
          line_color: '#555',
          draggable: true,
          hide_scrollbars_when_draggable: false,
          line_style: 'curved',
          node_overflow: 'wrap',
          expander_style: 'char',
        },
      });
      jm.show(cleanJsMindContent(source));
      setFailed(false);
    } catch (e) {
      // The file is model output, so an unparseable one is a real outcome
      // rather than a bug to swallow silently.
      console.warn('mind-map preview failed to render:', e);
      setFailed(true);
    }

    // jsMind binds every handler to the container it was given and nothing to
    // window, so emptying that container is the whole teardown.
    return () => {
      container.innerHTML = '';
    };
  }, [source]);

  return (
    <>
      {failed && (
        <div className="artifact-modal-note">
          {t('history.mindmapUnreadable', 'This mind map could not be drawn from its file.')}
        </div>
      )}
      <div ref={containerRef} className="artifact-modal-mindmap" />
    </>
  );
};

interface StageArtifactModalProps {
  sessionId: string;
  artifact: SessionArtifact;
  onClose: () => void;
}

/**
 * A past session's stage output, opened from the history detail.
 *
 * A pop-up rather than a screen: reading last Tuesday's summary is a glance,
 * and the history panel underneath is where the teacher came from and where
 * they are going back to.
 */
const StageArtifactModal: React.FC<StageArtifactModalProps> = ({
  sessionId,
  artifact,
  onClose,
}) => {
  const { t } = useTranslation();
  const [text, setText] = useState<string | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setText(null);

    getSessionArtifactText(sessionId, artifact.stage)
      .then((data) => {
        if (cancelled) return;
        setText(data.content);
        setTruncated(data.truncated);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId, artifact.stage]);

  const turns = useMemo(
    () => (artifact.kind === 'transcript' && text ? parseTranscript(text) : []),
    [artifact.kind, text],
  );

  // Both JSON kinds are written by a stage rather than by a model, so a parse
  // failure here means a truncated or half-written file: report it as one
  // instead of rendering an empty panel.
  const json = useMemo<{ topics?: Topic[]; stats?: ClassStats; error?: string }>(() => {
    if (!text || (artifact.kind !== 'topics' && artifact.kind !== 'stats')) return {};
    try {
      if (artifact.kind === 'topics') return { topics: parseTopics(text) };
      const parsed = JSON.parse(text);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('class_statistics.json is not an object');
      }
      return { stats: parsed as ClassStats };
    } catch (e) {
      return { error: e instanceof Error ? e.message : String(e) };
    }
  }, [artifact.kind, text]);

  const body = () => {
    if (error) return <div className="artifact-modal-error">{error}</div>;
    if (loading) return <div className="artifact-modal-note">{t('history.loading', 'Loading…')}</div>;

    if (artifact.kind === 'mindmap') {
      return <MindMapPreview source={text ?? ''} />;
    }

    if (artifact.kind === 'markdown') {
      return (
        <div className="artifact-modal-markdown">
          {/* The report embeds its mind map as /report/{session}/mindmap-image,
              which only resolves once it is pointed at the backend. */}
          <ReactMarkdown urlTransform={reportUrlTransform}>{text ?? ''}</ReactMarkdown>
        </div>
      );
    }

    if (artifact.kind === 'topics' || artifact.kind === 'stats') {
      if (json.error) {
        return (
          <div className="artifact-modal-error">
            {t('history.fileUnreadable', 'This file could not be read: {{reason}}', {
              reason: json.error,
            })}
          </div>
        );
      }
      if (artifact.kind === 'stats') {
        return <StatsPreview stats={json.stats ?? {}} />;
      }
      if (!json.topics?.length) {
        return (
          <div className="artifact-modal-note">
            {t('history.fileEmpty', 'This file is empty.')}
          </div>
        );
      }
      return (
        <table className="artifact-modal-topics">
          <thead>
            <tr>
              <th>{t('history.topicTime', 'When')}</th>
              <th>{t('history.topic', 'Topic')}</th>
            </tr>
          </thead>
          <tbody>
            {json.topics.map((topic, i) => (
              <tr key={`${topic.start_time}-${i}`}>
                <td className="artifact-topic-time">
                  {`${formatSecondsToTime(topic.start_time)} – ${formatSecondsToTime(topic.end_time)}`}
                </td>
                <td>{topic.topic}</td>
              </tr>
            ))}
          </tbody>
        </table>
      );
    }

    if (artifact.kind === 'transcript') {
      if (turns.length === 0) {
        return (
          <div className="artifact-modal-note">{t('history.fileEmpty', 'This file is empty.')}</div>
        );
      }
      return (
        <div className="artifact-modal-chat">
          {turns.map((turn) => (
            <div
              key={turn.id}
              className={`chat-row ${turn.isTeacher ? 'teacher-row' : 'student-row'}`}
            >
              <div className={`chat-bubble ${turn.isTeacher ? 'teacher-bubble' : 'student-bubble'}`}>
                {turn.speaker && <div className="speaker-label">{turn.speaker}</div>}
                <div className="speaker-text">{turn.text}</div>
              </div>
            </div>
          ))}
        </div>
      );
    }

    // A kind this build has no renderer for — an older UI against a newer
    // backend. Show the file rather than falling through to another kind's
    // renderer, which would report a perfectly good file as empty.
    return (
      <>
        <div className="artifact-modal-truncated">
          {t('history.kindUnknown', 'This app cannot lay out {{kind}} files yet; showing it raw.', {
            kind: artifact.kind,
          })}
        </div>
        <pre className="artifact-modal-raw">{text ?? ''}</pre>
      </>
    );
  };

  return (
    <Modal isOpen onClose={onClose} className="artifact-modal">
      <div className="artifact-modal-header">
        <div className="artifact-modal-title">
          {t(`history.stageName.${artifact.stage}`, artifact.stage)}
        </div>
        <div className="artifact-modal-filename">{artifact.filename}</div>
      </div>
      {truncated && (
        <div className="artifact-modal-truncated">
          {t('history.fileTruncated', 'This file is too long to show in full; the beginning is below.')}
        </div>
      )}
      <div
        className={`artifact-modal-body${artifact.kind === 'mindmap' && !error && !loading ? ' fill' : ''}`}
      >
        {body()}
      </div>
    </Modal>
  );
};

export default StageArtifactModal;
