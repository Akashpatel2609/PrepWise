// src/store/useInterviewStore.js
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export const useInterviewStore = create(
  persist(
    (set, get) => ({
      // core state
      sessionId: "",
      name: "",
      jobDescription: "",
      minutesPerQuestion: 1,
      totalTime: 1,
      numQuestions: 1,

      // asked questions & answers
      asked: [], // [{ question, responseText?, duration?, confidence?, timestamp? }]

      // actions
      initFromSetup: ({ name, jobDescription, minutesPerQuestion, totalTime, numQuestions }) => {
        const sessionId = (crypto?.randomUUID?.() || Math.random().toString(36).slice(2));
        localStorage.setItem("session_id", sessionId);
        localStorage.setItem("job_description", jobDescription);
        set({
          name,
          jobDescription,
          minutesPerQuestion: Math.max(1, minutesPerQuestion | 0),
          totalTime: Math.max(1, totalTime | 0),
          numQuestions: Math.max(1, numQuestions | 0),
          sessionId,
          asked: [],
        });
      },

      setSessionId: (id) => {
        localStorage.setItem("session_id", id);
        set({ sessionId: id });
      },

      addQuestion: (q) =>
        set((s) => ({ asked: [...s.asked, { question: q }] })),

      addTranscript: ({ question, responseText, duration, confidence, timestamp }) =>
        set((s) => {
          const arr = [...s.asked];
          // update the last matching question without transcript
          for (let i = arr.length - 1; i >= 0; i--) {
            if (arr[i].question === question && !arr[i].responseText) {
              arr[i] = { ...arr[i], responseText, duration, confidence, timestamp };
              return { asked: arr };
            }
          }
          // or append as a new item
          arr.push({ question, responseText, duration, confidence, timestamp });
          return { asked: arr };
        }),

      reset: () => {
        localStorage.removeItem("session_id");
        set({ sessionId: "", asked: [] });
      },
    }),
    {
      name: "interview-store",
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        sessionId: s.sessionId,
        name: s.name,
        jobDescription: s.jobDescription,
        minutesPerQuestion: s.minutesPerQuestion,
        totalTime: s.totalTime,
        numQuestions: s.numQuestions,
        asked: s.asked,
      }),
    }
  )
);
