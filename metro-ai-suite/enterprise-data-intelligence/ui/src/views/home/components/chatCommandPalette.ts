// Copyright (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

export enum CommandCategory {
  SESSION = "SESSION",
  MODEL = "MODEL",
  TOOL = "TOOL",
  AGENT = "AGENT",
}

export interface ChatCommandDefinition {
  command: string;
  category: CommandCategory;
  descriptionKey: string;
  keywords: string[];
}

export const COMMAND_CATEGORY_ORDER: CommandCategory[] = [
  CommandCategory.SESSION,
  CommandCategory.MODEL,
  CommandCategory.TOOL,
  CommandCategory.AGENT,
];

export const CHAT_COMMAND_DEFINITIONS: ChatCommandDefinition[] = [
  {
    command: "/session",
    category: CommandCategory.SESSION,
    descriptionKey: "chat.commandDescriptions.session",
    keywords: ["session", "settings", "idle"],
  },
  {
    command: "/new",
    category: CommandCategory.SESSION,
    descriptionKey: "chat.commandDescriptions.new",
    keywords: ["new", "session", "create"],
  },
  {
    command: "/stop",
    category: CommandCategory.SESSION,
    descriptionKey: "chat.commandDescriptions.stop",
    keywords: ["stop", "cancel", "run"],
  },
  {
    command: "/reset",
    category: CommandCategory.SESSION,
    descriptionKey: "chat.commandDescriptions.reset",
    keywords: ["reset", "restart", "session"],
  },
  {
    command: "/clear",
    category: CommandCategory.SESSION,
    descriptionKey: "chat.commandDescriptions.clear",
    keywords: ["clear", "history", "chat"],
  },
  {
    command: "/model",
    category: CommandCategory.MODEL,
    descriptionKey: "chat.commandDescriptions.model",
    keywords: ["model", "provider", "set"],
  },
  {
    command: "/models",
    category: CommandCategory.MODEL,
    descriptionKey: "chat.commandDescriptions.models",
    keywords: ["models", "provider", "list"],
  },
  {
    command: "/think",
    category: CommandCategory.MODEL,
    descriptionKey: "chat.commandDescriptions.think",
    keywords: ["think", "thinking", "reasoning"],
  },
  {
    command: "/help",
    category: CommandCategory.TOOL,
    descriptionKey: "chat.commandDescriptions.help",
    keywords: ["help", "commands", "guide"],
  },
  {
    command: "/tools",
    category: CommandCategory.TOOL,
    descriptionKey: "chat.commandDescriptions.tools",
    keywords: ["tools", "runtime", "list"],
  },
  {
    command: "/skill",
    category: CommandCategory.TOOL,
    descriptionKey: "chat.commandDescriptions.skill",
    keywords: ["skill", "run", "name"],
  },
  {
    command: "/status",
    category: CommandCategory.TOOL,
    descriptionKey: "chat.commandDescriptions.status",
    keywords: ["status", "state", "current"],
  },
  {
    command: "/tasks",
    category: CommandCategory.TOOL,
    descriptionKey: "chat.commandDescriptions.tasks",
    keywords: ["tasks", "background", "session"],
  },
  {
    command: "/agents",
    category: CommandCategory.AGENT,
    descriptionKey: "chat.commandDescriptions.agents",
    keywords: ["agents", "thread", "session"],
  },
  {
    command: "/subagents",
    category: CommandCategory.AGENT,
    descriptionKey: "chat.commandDescriptions.subagents",
    keywords: ["subagents", "spawn", "kill", "log", "steer"],
  },
];
