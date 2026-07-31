

import { defineStore } from "pinia";

export const sessionAppStore = defineStore("session", {
  state: () => ({
    responseSession: "",
    currentSession: "",
  }),
  persist: {
    key: "sessionInfo",
    storage: sessionStorage,
  },
  actions: {
    setResponseSessionId(sessionId: string) {
      this.responseSession = sessionId;
    },
    setSessionId(sessionId: string) {
      this.currentSession = sessionId;
    },
  },
});
