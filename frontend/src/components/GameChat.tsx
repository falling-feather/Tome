import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../api/client';
import { playMessageSound, sendNotification } from '../utils/sound';

interface Segment {
  speaker: string;   // "narrator" | 角色名
  content: string;
}

interface Message {
  id?: number;
  role: string;
  content: string;
  created_at?: string;
  segments?: Segment[];
  metadata_?: Record<string, any>;
}

interface GameChatProps {
  sessionId: string;
  messages: Message[];
  onMessagesUpdate: (messages: Message[], state?: any) => void;
}

/** 实时解析流式文本中的 [旁白]/[角色:XXX] 标签为段落 */
function parseSegmentsRealtime(text: string): Segment[] | null {
  const tagRegex = /^\[(旁白|角色[:：](.+?))\]\s*$/gm;
  let match;
  const tags: { index: number; end: number; speaker: string }[] = [];

  while ((match = tagRegex.exec(text)) !== null) {
    const speaker = match[2] ? match[2].trim() : 'narrator';
    tags.push({ index: match.index, end: match.index + match[0].length, speaker });
  }

  if (tags.length === 0) return null;

  const segments: Segment[] = [];
  const before = text.slice(0, tags[0].index).trim();
  if (before) {
    segments.push({ speaker: 'narrator', content: before });
  }

  for (let i = 0; i < tags.length; i++) {
    const start = tags[i].end;
    const end = i + 1 < tags.length ? tags[i + 1].index : text.length;
    const content = text.slice(start, end).trim();
    if (content) {
      segments.push({ speaker: tags[i].speaker, content });
    }
  }

  return segments.length > 0 ? segments : null;
}

export function GameChat({ sessionId, messages, onMessagesUpdate }: GameChatProps) {
  const { t } = useTranslation();
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamPhase, setStreamPhase] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const userAtBottomRef = useRef(true);
  const abortRef = useRef<AbortController | null>(null);
  // rAF batching: avoid React re-render per token to prevent jank on slow devices.
  const pendingFlushRef = useRef<number | null>(null);
  const pendingMessagesRef = useRef<Message[] | null>(null);
  const pendingStateRef = useRef<any>(undefined);

  const scheduleFlush = useCallback((updated: Message[], state?: any) => {
    pendingMessagesRef.current = updated;
    if (state !== undefined) pendingStateRef.current = state;
    if (pendingFlushRef.current != null) return;
    pendingFlushRef.current = requestAnimationFrame(() => {
      pendingFlushRef.current = null;
      const msgs = pendingMessagesRef.current;
      const st = pendingStateRef.current;
      pendingMessagesRef.current = null;
      pendingStateRef.current = undefined;
      if (msgs) onMessagesUpdate(msgs, st);
    });
  }, [onMessagesUpdate]);

  useEffect(() => () => {
    if (pendingFlushRef.current != null) cancelAnimationFrame(pendingFlushRef.current);
    abortRef.current?.abort();
  }, []);

  /** 检测用户是否在聊天底部附近 */
  const checkIfAtBottom = useCallback(() => {
    const el = chatContainerRef.current;
    if (!el) return;
    const threshold = 80;
    userAtBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  }, []);

  /** 仅在用户位于底部时自动滚动 */
  useEffect(() => {
    if (userAtBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleSubmit = async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    setInput('');
    setIsStreaming(true);
    setStreamPhase('提交中…');

    const userMsg: Message = { role: 'user', content: text };
    const updatedMessages = [...messages, userMsg];
    onMessagesUpdate(updatedMessages);

    // Add placeholder for assistant response (streaming)
    const assistantMsg: Message = { role: 'assistant', content: '' };
    const withAssistant = [...updatedMessages, assistantMsg];
    onMessagesUpdate(withAssistant);

    try {
      let fullContent = '';
      const ac = new AbortController();
      abortRef.current = ac;
      const iterator = api.submitAction(sessionId, text, {
        signal: ac.signal,
        onRetry: (n) => setStreamPhase(`连接断开，正在重连…(第 ${n} 次)`),
      });
      for await (const data of iterator) {
        if (data.phase === 'validated') {
          setStreamPhase('叙事生成中…');
        } else if (data.phase === 'event_triggered') {
          const evt = data.event || {};
          setStreamPhase(`事件触发：${evt.title || evt.event_key || '未知'}`);
        } else if (data.phase === 'extracted') {
          setStreamPhase('后处理中…');
        } else if (data.phase === 'audit') {
          setStreamPhase(data.audit?.rewritten ? '审核改写中…' : '审核完成');
        }
        if (data.content) {
          fullContent += data.content;
          const updated = [...updatedMessages, { role: 'assistant', content: fullContent }];
          scheduleFlush(updated);
        }
        if (data.done) {
          // Parse segments from done event
          const segments: Segment[] = data.segments || [];
          const finalMsg: Message = {
            role: 'assistant',
            content: fullContent,
            segments: segments.length > 0 ? segments : undefined,
          };
          // Force-flush final state synchronously (cancel pending rAF).
          if (pendingFlushRef.current != null) {
            cancelAnimationFrame(pendingFlushRef.current);
            pendingFlushRef.current = null;
          }
          onMessagesUpdate([...updatedMessages, finalMsg], data.state || undefined);
          // 音效 & 通知
          playMessageSound();
          sendNotification('不存在之书', fullContent.slice(0, 80) + (fullContent.length > 80 ? '...' : ''));
        }
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        const abortMsg: Message = { role: 'system', content: t('game.stopped') };
        onMessagesUpdate([...updatedMessages, abortMsg]);
      } else {
        const errorMsg: Message = { role: 'system', content: `错误：${err.message}` };
        onMessagesUpdate([...updatedMessages, errorMsg]);
      }
    } finally {
      abortRef.current = null;
      setIsStreaming(false);
      setStreamPhase('');
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const autoResize = () => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }
  };

  const formatContent = (content: string) => {
    return content.split('\n').map((line, i) => (
      <p key={i}>{line || '\u00A0'}</p>
    ));
  };

  /** 获取消息的分段：优先 segments 字段，其次 metadata_ 中存储的 */
  const getSegments = (msg: Message): Segment[] | undefined => {
    if (msg.segments && msg.segments.length > 0) return msg.segments;
    if (msg.metadata_?.segments && msg.metadata_.segments.length > 0) return msg.metadata_.segments;
    return undefined;
  };

  /** 渲染单个分段 */
  const renderSegment = (seg: Segment, idx: number) => {
    const isNarrator = seg.speaker === 'narrator';
    return (
      <div key={idx} className={`chat-segment ${isNarrator ? 'segment-narrator' : 'segment-character'}`}>
        <div className="segment-avatar">
          {isNarrator ? '📖' : seg.speaker[0]}
        </div>
        <div className="segment-body">
          {!isNarrator && <div className="segment-speaker">{seg.speaker}</div>}
          <div className="segment-text">{formatContent(seg.content)}</div>
        </div>
      </div>
    );
  };

  /** 渲染一条消息（可能包含多个分段） */
  const renderMessage = (msg: Message, i: number) => {
    // 用户消息 / 系统消息 — 保持原样
    if (msg.role === 'user' || msg.role === 'system') {
      return (
        <div key={i} className={`chat-msg ${msg.role}`}>
          <div className="msg-avatar">
            {msg.role === 'user' ? '你' : '!'}
          </div>
          <div>
            <div className="msg-body">{formatContent(msg.content)}</div>
            {msg.created_at && <div className="msg-time">{new Date(msg.created_at).toLocaleTimeString('zh-CN')}</div>}
          </div>
        </div>
      );
    }

    // 助手消息 — 检查是否有分段
    const segments = getSegments(msg);
    const isStreamingMsg = isStreaming && i === messages.length - 1;

    // 流式传输中 — 尝试实时解析段落
    if (!segments && isStreamingMsg) {
      const liveSegments = msg.content ? parseSegmentsRealtime(msg.content) : null;
      if (liveSegments) {
        return (
          <div key={i} className="chat-dialogue-group">
            {liveSegments.map((seg, idx) => renderSegment(seg, idx))}
          </div>
        );
      }
    }

    // 流式传输中或无分段 — 单行显示
    if (!segments) {
      return (
        <div key={i} className="chat-msg assistant">
          <div className="msg-avatar">📖</div>
          <div>
            <div className="msg-body">
              {formatContent(msg.content || (isStreaming && i === messages.length - 1 ? '...' : ''))}
            </div>
            {msg.created_at && <div className="msg-time">{new Date(msg.created_at).toLocaleTimeString('zh-CN')}</div>}
          </div>
        </div>
      );
    }

    // 多分段 — 渲染为对话组
    return (
      <div key={i} className="chat-dialogue-group">
        {segments.map((seg, idx) => renderSegment(seg, idx))}
        {msg.created_at && <div className="msg-time dialogue-time">{new Date(msg.created_at).toLocaleTimeString('zh-CN')}</div>}
      </div>
    );
  };

  return (
    <div className="game-area">
      <div className="chat-messages" ref={chatContainerRef} onScroll={checkIfAtBottom}>
        {messages.map((msg, i) => renderMessage(msg, i))}
        {isStreaming && messages[messages.length - 1]?.role === 'assistant' && (
          <div className="chat-typing">
            <div className="typing-dots"><span /><span /><span /></div>
            {streamPhase || '正在叙述...'}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <div className="chat-input-row">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => { setInput(e.target.value); autoResize(); }}
            onKeyDown={handleKeyDown}
            placeholder={t('game.inputPlaceholder')}
            disabled={isStreaming}
            rows={1}
          />
          <button className="btn btn-primary" onClick={handleSubmit} disabled={isStreaming || !input.trim()}>
            {isStreaming ? <span className="spinner" /> : t('game.send')}
          </button>
          {isStreaming && (
            <button className="btn btn-ghost" onClick={handleStop} title={t('game.stop')}>
              {t('game.stop')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
