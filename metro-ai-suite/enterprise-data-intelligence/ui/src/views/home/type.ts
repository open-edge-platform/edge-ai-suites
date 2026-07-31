// 知识库摘要（左侧列表）
export interface KnowledgeBaseSummary {
  id: string;
  name: string;
  description?: string;
  updatedAt: string;
}

// 文档条目
export interface DocumentItem {
  id: string;
  name: string;
  type: string; // 例如 'csv', 'pdf', 'docx'
  size: string; // 文件大小，如 "1.2 MB"
  updatedAt: string;
}

// 知识库详情（右侧完整信息）
export interface KnowledgeBaseDetail {
  id: string;
  name: string;
  description: string;
  documents: DocumentItem[];
}

export type AssistantBlockKind = "agent";
export type AssistantAgentLevel = "main" | "sub" | "none";

export interface AssistantBlock {
  id: string;
  kind: AssistantBlockKind;
  agentLevel: AssistantAgentLevel;
  title: string;
  content: string;
  isCompleted: boolean;
  isToolActive?: boolean;
}

export interface UserChatMessage {
  role: "user";
  content: string;
}

export interface AssistantChatMessage {
  role: "assistant";
  content: string;
  isCompleted: boolean;
  blocks: AssistantBlock[];
}

export type ChatMessage = UserChatMessage | AssistantChatMessage;

export interface StreamDisplayEvent {
  kind: AssistantBlockKind;
  blockId: string;
  agentLevel: AssistantAgentLevel;
  title: string;
  content: string;
  replace?: boolean;
  done?: boolean;
  isToolActive?: boolean;
}
